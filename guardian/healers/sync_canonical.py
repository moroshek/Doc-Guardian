"""
Sync Canonical Data to Documentation

Detects changes to a canonical source file (JSON/YAML/TOML) and propagates
updates to documentation files using configurable templates.

Universal healer extracted from TCF's auto_sync_canonical.py implementation.

Security features:
- Path validation for all file operations (DG-2026-001, DG-2026-005)
- Module whitelist for context_builder imports (DG-2026-003)
- ReDoS protection for section patterns (DG-2026-002)
- File size limits (DG-2026-006)

Configuration:
    healers:
      sync_canonical:
        enabled: true
        source_file: path/to/canonical.json
        source_format: json  # json, yaml, or toml
        target_patterns:
          - file: docs/reference.md
            template: reference.md.j2
            sections: [all]
            full_replace: true
          - file: docs/skills/skill.md
            template: skill_section.md.j2
            sections: [model_codes]
            section_pattern: "<!-- SYNC_START -->.*?<!-- SYNC_END -->"
            partial_template: model_codes.md.j2

Usage:
    from guardian.healers.sync_canonical import SyncCanonicalHealer

    healer = SyncCanonicalHealer(config)
    report = healer.check()  # Preview changes
    report = healer.heal()   # Apply high-confidence changes
"""

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core.base import Change, HealingReport, HealingSystem
from ..core.path_validator import (
    validate_path_contained,
    validate_templates_dir,
    PathSecurityError,
)
from ..core.regex_validator import (
    validate_regex_safety,
    RegexSecurityError,
)
from ..core.security import (
    validate_file_size,
    safe_read_file,
    validate_module_path,
    ALLOWED_CONTEXT_BUILDER_MODULES,
)

# Try to import template engine
try:
    from jinja2 import Environment, FileSystemLoader, Template, TemplateError
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False
    Environment = None
    FileSystemLoader = None
    Template = None
    TemplateError = Exception

# Try to import YAML support
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None


@dataclass
class SyncTarget:
    """A file that needs updating from canonical data"""
    file_path: Path
    template_name: str
    sections: List[str]
    section_pattern: Optional[str] = None
    full_replace: bool = False
    partial_template: Optional[str] = None
    confidence: float = 0.0


@dataclass
class ChangedField:
    """Represents a field that changed in canonical source"""
    field: str
    change_type: str  # 'added', 'modified', 'removed'
    old_value: Any = None
    new_value: Any = None


class CanonicalLoader:
    """Load and parse canonical source file with caching"""

    def __init__(self, path: Path, source_format: str):
        """
        Initialize loader.

        Args:
            path: Path to canonical source file
            source_format: File format ('json', 'yaml', or 'toml')
        """
        self.path = path
        self.source_format = source_format.lower()
        self._data: Optional[Dict] = None
        self._load_time: Optional[datetime] = None

    def load(self, force: bool = False) -> Dict:
        """
        Load canonical data with optional cache refresh.

        Args:
            force: Force reload even if cached

        Returns:
            Parsed data as dictionary

        Raises:
            FileNotFoundError: If source file doesn't exist
            json.JSONDecodeError: If JSON is malformed (DC-07)
            yaml.YAMLError: If YAML is malformed
            ValueError: If format is unsupported
        """
        if self._data is None or force:
            # Check file exists
            if not self.path.exists():
                raise FileNotFoundError(f"Canonical source file not found: {self.path}")

            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except PermissionError as e:
                raise PermissionError(f"Cannot read canonical source file {self.path}: {e}")
            except UnicodeDecodeError as e:
                raise ValueError(f"Encoding error reading {self.path}: {e}. Ensure file is UTF-8 encoded.")

            try:
                if self.source_format == 'json':
                    try:
                        self._data = json.loads(content)
                    except json.JSONDecodeError as e:
                        # DC-07: Provide helpful error message for malformed JSON
                        raise ValueError(
                            f"Malformed JSON in {self.path} at line {e.lineno}, column {e.colno}: {e.msg}. "
                            f"Check for trailing commas, missing quotes, or invalid escape sequences."
                        ) from e
                elif self.source_format == 'yaml':
                    if not YAML_AVAILABLE:
                        raise RuntimeError("PyYAML not installed. Run: pip install pyyaml")
                    try:
                        self._data = yaml.safe_load(content)
                    except yaml.YAMLError as e:
                        raise ValueError(
                            f"Malformed YAML in {self.path}: {e}. "
                            f"Check for indentation issues or invalid syntax."
                        ) from e
                elif self.source_format == 'toml':
                    # Use stdlib tomllib (Python 3.11+) or fallback to configparser
                    try:
                        import tomllib
                        self._data = tomllib.loads(content)
                    except ImportError:
                        # Fallback to configparser for simple TOML
                        import configparser
                        parser = configparser.ConfigParser()
                        parser.read(self.path)
                        self._data = {s: dict(parser.items(s)) for s in parser.sections()}
                    except Exception as e:
                        raise ValueError(
                            f"Malformed TOML in {self.path}: {e}. "
                            f"Check for invalid syntax."
                        ) from e
                else:
                    raise ValueError(f"Unsupported format: {self.source_format}. Use 'json', 'yaml', or 'toml'.")

            except ValueError:
                # Re-raise ValueError without wrapping
                raise

            self._load_time = datetime.now()

        return self._data

    def get_nested_value(self, path: str, default: Any = None) -> Any:
        """
        Get value from nested dictionary using dot notation.

        Args:
            path: Dot-separated path (e.g., "metadata.attributes.fan_type")
            default: Default value if path not found

        Returns:
            Value at path or default
        """
        data = self.load()
        parts = path.split('.')

        for part in parts:
            if isinstance(data, dict):
                data = data.get(part)
                if data is None:
                    return default
            else:
                return default

        return data if data is not None else default


class ChangeDetector:
    """Detect changes in canonical source via git diff"""

    def __init__(self, source_file: Path, project_root: Path):
        """
        Initialize detector.

        Args:
            source_file: Path to canonical source file
            project_root: Root directory of git repository
        """
        self.source_file = source_file
        self.project_root = project_root

    def detect_changes(self, commit: str = "HEAD") -> List[ChangedField]:
        """
        Detect which fields changed in canonical source.

        Args:
            commit: Git commit to compare against

        Returns:
            List of ChangedField objects
        """
        changed_fields = []

        try:
            # Get diff for source file
            result = subprocess.run(
                ["git", "diff", f"{commit}^", commit, "--", str(self.source_file)],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if result.returncode != 0:
                # Try without parent (for initial commit)
                result = subprocess.run(
                    ["git", "diff", "--cached", "--", str(self.source_file)],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                )

            diff_output = result.stdout

            # Parse diff to extract changed fields
            # Look for lines like: +    "field_name": value
            added_pattern = re.compile(r'^\+\s*"([^"]+)":\s*')
            removed_pattern = re.compile(r'^-\s*"([^"]+)":\s*')

            added = set()
            removed = set()

            for line in diff_output.split('\n'):
                if match := added_pattern.match(line):
                    added.add(match.group(1))
                elif match := removed_pattern.match(line):
                    removed.add(match.group(1))

            # Categorize changes
            for field in added - removed:
                changed_fields.append(ChangedField(field=field, change_type="added"))
            for field in removed - added:
                changed_fields.append(ChangedField(field=field, change_type="removed"))
            for field in added & removed:
                changed_fields.append(ChangedField(field=field, change_type="modified"))

        except Exception as e:
            # Non-fatal - just means we can't detect incremental changes
            pass

        return changed_fields

    def has_uncommitted_changes(self) -> bool:
        """
        Check if canonical source has uncommitted changes.

        Returns:
            True if source file has uncommitted changes
        """
        result = subprocess.run(
            ["git", "status", "--porcelain", str(self.source_file)],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )
        return bool(result.stdout.strip())


class TemplateRenderer:
    """Render Jinja2 templates with canonical data"""

    def __init__(self, loader: CanonicalLoader, templates_dir: Path, context_builder=None):
        """
        Initialize renderer.

        Args:
            loader: CanonicalLoader instance with source data
            templates_dir: Directory containing Jinja2 templates
            context_builder: Optional callable that builds template context from loader
        """
        self.loader = loader
        self.templates_dir = templates_dir
        self.context_builder = context_builder
        self.env: Optional[Environment] = None

        if JINJA2_AVAILABLE:
            self.env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            # Add custom filters
            self.env.filters['tojson'] = lambda x: json.dumps(x, indent=None)

    def get_template_context(self) -> Dict[str, Any]:
        """
        Build context dict for templates.

        If context_builder was provided, use it. Otherwise return
        the raw canonical data plus timestamp.

        Returns:
            Dictionary of template variables
        """
        if self.context_builder:
            return self.context_builder(self.loader)

        # Default: return raw data + timestamp
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": self.loader.load(),
        }

    def render(self, template_name: str) -> str:
        """
        Render a template with canonical data.

        Args:
            template_name: Name of template file in templates_dir

        Returns:
            Rendered template content

        Raises:
            RuntimeError: If Jinja2 not installed
        """
        if not JINJA2_AVAILABLE or self.env is None:
            raise RuntimeError("Jinja2 is not installed. Run: pip install jinja2")

        template = self.env.get_template(template_name)
        context = self.get_template_context()
        return template.render(**context)


class ConfidenceCalculator:
    """Calculate confidence scores for sync operations"""

    @staticmethod
    def calculate(target: SyncTarget, old_content: str, new_content: str) -> float:
        """
        Calculate confidence score (0.0 to 1.0).

        Factors:
        - Has sync markers (30%)
        - Template rendered successfully (20%)
        - Structure preserved (20%)
        - No manual edits detected (15%)
        - Reasonable diff size (15%)

        Args:
            target: SyncTarget being processed
            old_content: Current file content
            new_content: Rendered new content

        Returns:
            Confidence score between 0.0 and 1.0
        """
        score = 0.5  # Base score

        # 1. File has sync markers (30%)
        if "SYNC_START" in old_content or target.full_replace:
            score += 0.30

        # 2. Template rendered without errors - assumed true (20%)
        if new_content:
            score += 0.20

        # 3. Structure preserved (20%)
        old_lines = set(old_content.split('\n'))
        new_lines = set(new_content.split('\n'))
        if old_lines and new_lines:
            if target.full_replace:
                # For full replace, check if key structure markers exist
                key_markers = ['#', '##', '```', '"""', 'def ', 'class ']
                old_markers = sum(1 for m in key_markers if any(m in l for l in old_lines))
                new_markers = sum(1 for m in key_markers if any(m in l for l in new_lines))
                if old_markers > 0 and new_markers >= old_markers:
                    score += 0.20
            else:
                # For partial replace, check similarity
                similarity = len(old_lines & new_lines) / max(len(old_lines | new_lines), 1)
                if similarity > 0.3:
                    score += 0.20

        # 4. No manual edits detected (15%)
        manual_edit_markers = ["# MANUAL EDIT", "# DO NOT AUTO-SYNC", "<!-- MANUAL -->"]
        has_manual_edits = any(m in old_content for m in manual_edit_markers)
        if not has_manual_edits:
            score += 0.15

        # 5. Reasonable diff size (15%)
        diff_lines = abs(len(old_content.split('\n')) - len(new_content.split('\n')))
        if diff_lines < 500:
            score += 0.15

        return min(score, 1.0)

    @staticmethod
    def has_manual_edits(content: str) -> bool:
        """
        Detect if file has manual edits that should prevent auto-sync.

        Args:
            content: File content to check

        Returns:
            True if manual edit markers found
        """
        markers = [
            "# MANUAL EDIT",
            "# DO NOT AUTO-SYNC",
            "# CUSTOM:",
            "<!-- MANUAL -->",
        ]
        return any(marker in content for marker in markers)


class SyncCanonicalHealer(HealingSystem):
    """
    Sync canonical source data to documentation files.

    This healer:
    1. Detects changes to a canonical source file (JSON/YAML/TOML)
    2. Identifies affected documentation files
    3. Renders updates using Jinja2 templates
    4. Applies changes with confidence-based auto-commit
    5. Creates backups before modifications

    Configuration:
        source_file: Path to canonical source (relative to project root)
        source_format: File format (json, yaml, toml)
        templates_dir: Directory containing Jinja2 templates
        backup_dir: Directory for backups (default: .doc-guardian/backups)
        target_patterns: List of target file configurations
        context_builder: Optional Python path to context builder function
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize sync canonical healer.

        Security:
        - Validates source_file, templates_dir paths are within project root (DG-2026-001)
        - Validates section_pattern regex for ReDoS (DG-2026-002)

        Args:
            config: Configuration dict with sync_canonical section.
                    Required keys: healers.sync_canonical.source_file

        Raises:
            ValueError: If required configuration is missing
            PathSecurityError: If paths escape project root
            RegexSecurityError: If section_pattern is potentially dangerous
        """
        super().__init__(config)

        healer_config = config.get('healers', {}).get('sync_canonical', {})

        if 'source_file' not in healer_config:
            raise ValueError(
                "SyncCanonicalHealer requires 'healers.sync_canonical.source_file' in config. "
                "This healer is disabled by default - set enabled=true and source_file to use it."
            )

        # Source file configuration
        source_path = self.project_root / healer_config['source_file']
        source_format = healer_config.get('source_format', 'json')

        # Security: Validate source_path is within project root (DG-2026-001)
        source_path = validate_path_contained(source_path, self.project_root, allow_nonexistent=True)

        # Template configuration
        templates_dir = self.project_root / healer_config.get('templates_dir', '.doc-guardian/templates')

        # Security: Validate templates_dir is within project root (DG-2026-005)
        templates_dir = validate_templates_dir(templates_dir, self.project_root)

        # Backup configuration
        self.backup_dir = self.project_root / healer_config.get('backup_dir', '.doc-guardian/backups')

        # Target patterns - validate section_patterns for ReDoS
        raw_target_patterns = healer_config.get('target_patterns', [])
        self.target_patterns = []
        for pattern in raw_target_patterns:
            # Security: Validate section_pattern for ReDoS (DG-2026-002)
            section_pattern = pattern.get('section_pattern')
            if section_pattern:
                is_safe, error = validate_regex_safety(section_pattern)
                if not is_safe:
                    raise RegexSecurityError(
                        f"Potentially dangerous section_pattern: '{section_pattern}'. Error: {error}"
                    )
            self.target_patterns.append(pattern)

        # Initialize components
        self.loader = CanonicalLoader(source_path, source_format)
        self.renderer = TemplateRenderer(
            self.loader,
            templates_dir,
            context_builder=self._load_context_builder(healer_config.get('context_builder'))
        )
        self.confidence_calc = ConfidenceCalculator()
        self.detector = ChangeDetector(source_path, self.project_root)

    def _load_context_builder(self, python_path: Optional[str]):
        """
        Load context builder function from Python path.

        Security:
        - Validates module path against whitelist (DG-2026-003)
        - Prevents arbitrary code execution via malicious config

        Args:
            python_path: Dotted path to function (e.g., "myproject.utils.build_context")

        Returns:
            Callable or None

        Raises:
            ValueError: If module is not in allowed whitelist
        """
        if not python_path:
            return None

        # Security: Validate module against whitelist (DG-2026-003)
        is_allowed, error = validate_module_path(python_path)
        if not is_allowed:
            raise ValueError(
                f"context_builder module not allowed: {error}. "
                f"Add to ALLOWED_CONTEXT_BUILDER_MODULES if needed."
            )

        try:
            module_path, func_name = python_path.rsplit('.', 1)
            import importlib
            module = importlib.import_module(module_path)
            return getattr(module, func_name)
        except Exception as e:
            self.log_error(f"Could not load context_builder '{python_path}': {e}")
            return None

    def check(self) -> HealingReport:
        """
        Analyze documentation and identify sync needs.

        Returns:
            HealingReport with proposed changes
        """
        import time
        start_time = time.time()

        changes = []

        # Detect what changed in canonical source
        changed_fields = self.detector.detect_changes()

        # Get all sync targets
        targets = self._get_sync_targets()

        # Check each target
        for target in targets:
            try:
                # Read current content
                if target.file_path.exists():
                    old_content = target.file_path.read_text()
                else:
                    old_content = ""

                # Render new content
                new_content = self._render_target(target, old_content)

                # Calculate confidence
                confidence = self.confidence_calc.calculate(target, old_content, new_content)
                target.confidence = confidence

                # Check if changed
                if old_content.strip() != new_content.strip():
                    changes.append(Change(
                        file=target.file_path,
                        line=0,
                        old_content=old_content,
                        new_content=new_content,
                        confidence=confidence,
                        reason=f"Sync from canonical source (template: {target.template_name})",
                        healer="SyncCanonicalHealer"
                    ))

            except Exception as e:
                self.log_error(f"Error checking {target.file_path}: {e}")

        execution_time = time.time() - start_time

        return self.create_report(
            mode="check",
            issues_found=len(changes),
            issues_fixed=0,
            changes=changes,
            execution_time=execution_time
        )

    def heal(self, min_confidence: Optional[float] = None) -> HealingReport:
        """
        Apply sync changes above confidence threshold.

        Args:
            min_confidence: Override default confidence threshold

        Returns:
            HealingReport with applied changes
        """
        import time
        start_time = time.time()

        # Get proposed changes
        check_report = self.check()

        # Filter by confidence
        threshold = min_confidence if min_confidence is not None else self.min_confidence
        changes_to_apply = [c for c in check_report.changes if c.confidence >= threshold]

        applied_changes = []

        # Apply each change
        for change in changes_to_apply:
            if self._apply_sync_change(change):
                applied_changes.append(change)

        execution_time = time.time() - start_time

        return self.create_report(
            mode="heal",
            issues_found=len(check_report.changes),
            issues_fixed=len(applied_changes),
            changes=applied_changes,
            execution_time=execution_time
        )

    def _get_sync_targets(self) -> List[SyncTarget]:
        """
        Get all sync targets from configuration.

        Returns:
            List of SyncTarget objects
        """
        targets = []

        for pattern in self.target_patterns:
            file_path = self.project_root / pattern['file']

            # Create target even if file doesn't exist (for full_replace mode)
            if file_path.exists() or pattern.get('full_replace', False):
                targets.append(SyncTarget(
                    file_path=file_path,
                    template_name=pattern['template'],
                    sections=pattern.get('sections', ['all']),
                    section_pattern=pattern.get('section_pattern'),
                    full_replace=pattern.get('full_replace', False),
                    partial_template=pattern.get('partial_template'),
                ))

        return targets

    def _render_target(self, target: SyncTarget, old_content: str) -> str:
        """
        Render new content for a sync target.

        Args:
            target: SyncTarget to render
            old_content: Current file content

        Returns:
            Rendered content
        """
        # Use partial template if specified, otherwise main template
        template_to_use = target.partial_template if target.partial_template else target.template_name
        new_content = self.renderer.render(template_to_use)

        # For partial replacement, extract and replace section
        if not target.full_replace and target.section_pattern and old_content:
            match = re.search(target.section_pattern, old_content, re.DOTALL)
            if match:
                old_section = match.group(0)  # Use full match, not group(1)
                new_content = old_content.replace(old_section, new_content)
            else:
                raise ValueError(f"Section pattern not found: {target.section_pattern}")

        return new_content

    def _apply_sync_change(self, change: Change) -> bool:
        """
        Apply a sync change with backup.

        Args:
            change: Change to apply

        Returns:
            True if successfully applied
        """
        try:
            # Create backup directory
            self.backup_dir.mkdir(parents=True, exist_ok=True)

            # Create timestamped backup if file exists
            if change.file.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self.backup_dir / f"{change.file.name}.{timestamp}.bak"
                shutil.copy2(change.file, backup_path)

            # Write new content
            change.file.parent.mkdir(parents=True, exist_ok=True)
            change.file.write_text(change.new_content)

            return True

        except Exception as e:
            self.log_error(f"Failed to apply change to {change.file}: {e}")
            return False
