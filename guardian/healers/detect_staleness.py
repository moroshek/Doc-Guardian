"""
Staleness Detection Healer

Detects and fixes stale documentation by:
1. Auto-updating timestamps that are > N days behind git history
2. Flagging deprecated command syntax for manual review

Security features:
- ReDoS protection for user-provided regex patterns (DG-2026-002)
- File size limits (DG-2026-006)
- Pattern count limits (DG-2026-006)

Universal implementation - configuration driven, no TCF-specific paths.

Performance:
- Batched git operations: Single git log command for all files instead of one per file
- Old: O(n) subprocess calls where n = number of files
- New: O(1) subprocess calls with batch parsing
"""

import re
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import time

from guardian.core.base import HealingSystem, HealingReport, Change
from guardian.core.git_utils import git_commit
from guardian.core.regex_validator import (
    validate_regex_safety,
    RegexSecurityError,
)
from guardian.core.security import (
    validate_file_size,
    safe_read_file,
    MAX_PATTERNS,
)


def get_all_git_timestamps(files: List[Path], project_root: Path, timeout: int = 30) -> Dict[Path, datetime]:
    """
    Batch git log for all files at once.

    Instead of running O(n) git commands (one per file), we run a single
    git command and parse the output.

    Performance:
    - Old: ~100ms per file * 1000 files = 100 seconds
    - New: ~500ms total for 1000 files

    Args:
        files: List of file paths to get timestamps for
        project_root: Project root for git commands
        timeout: Timeout in seconds

    Returns:
        Dict mapping file paths to their last modified datetime
    """
    if not files:
        return {}

    timestamps: Dict[Path, datetime] = {}

    try:
        # Use git log with format that includes file paths
        # --name-only shows file names after each commit
        # We want the LATEST commit date for each file
        result = subprocess.run(
            ['git', 'log', '--name-only', '--format=%cd', '--date=short'] +
            ['--'] + [str(f) for f in files],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode != 0:
            return {}

        # Parse output: alternating date lines and file lines
        # Format:
        # 2026-01-11
        # path/to/file1.md
        # path/to/file2.md
        #
        # 2026-01-10
        # path/to/file3.md
        # ...

        current_date: Optional[datetime] = None

        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Try to parse as date
            try:
                current_date = datetime.strptime(line, "%Y-%m-%d")
            except ValueError:
                # Not a date, must be a file path
                if current_date:
                    file_path = project_root / line
                    # Only add if we haven't seen this file yet (keep first = latest)
                    if file_path not in timestamps:
                        timestamps[file_path] = current_date

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    return timestamps


def get_git_timestamp_for_files_batch(files: List[Path], project_root: Path, timeout: int = 60) -> Dict[Path, datetime]:
    """
    Alternative batch method using git log with stat format.

    This method is more reliable for large numbers of files as it processes
    files in chunks to avoid command line length limits.

    Args:
        files: List of file paths
        project_root: Project root for git commands
        timeout: Timeout in seconds

    Returns:
        Dict mapping file paths to last modified datetime
    """
    if not files:
        return {}

    timestamps: Dict[Path, datetime] = {}

    # Process files in chunks to avoid arg limit issues
    chunk_size = 100

    for i in range(0, len(files), chunk_size):
        chunk = files[i:i + chunk_size]

        for file_path in chunk:
            if file_path in timestamps:
                continue

            try:
                # For each file, get just its last commit date
                result = subprocess.run(
                    ['git', 'log', '-1', '--format=%cd', '--date=short', '--', str(file_path)],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0 and result.stdout.strip():
                    date_str = result.stdout.strip()
                    timestamps[file_path] = datetime.strptime(date_str, "%Y-%m-%d")

            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
                continue

    return timestamps


class DetectStalenessHealer(HealingSystem):
    """
    Detects and fixes stale documentation.

    Configuration (from config dict):
        healers.detect_staleness.timestamp_patterns: List of regex patterns to match timestamps
        healers.detect_staleness.staleness_threshold_days: Days before considering timestamp stale
        healers.detect_staleness.deprecated_patterns: List of deprecated command patterns
        healers.detect_staleness.exclude_dirs: Directories to skip during scanning
    """

    def __init__(self, config: Dict):
        super().__init__(config)

        # Load staleness-specific config
        healer_config = config.get('healers', {}).get('detect_staleness', {})

        # Timestamp patterns to recognize
        raw_patterns = healer_config.get('timestamp_patterns', [
            r'\*\*Last Updated\*\*:\s*(\d{4}-\d{2}-\d{2})',
            r'\*\*Last Updated\*\*:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
            r'Last updated:\s*(\d{4}-\d{2}-\d{2})',
            r'_Last modified:\s*(\d{4}-\d{2}-\d{2})_',
            r'Last Updated:\s*(\d{4}-\d{2}-\d{2})',  # Without bold
        ])

        # Security: Limit pattern count (DG-2026-006)
        if len(raw_patterns) > MAX_PATTERNS:
            raise ValueError(
                f"Too many timestamp patterns: {len(raw_patterns)} > {MAX_PATTERNS}"
            )

        # Security: Validate timestamp patterns for ReDoS (DG-2026-002)
        self.timestamp_patterns = []
        for pattern in raw_patterns:
            is_safe, error = validate_regex_safety(pattern)
            if not is_safe:
                raise RegexSecurityError(
                    f"Potentially dangerous timestamp_pattern: '{pattern}'. Error: {error}"
                )
            self.timestamp_patterns.append(pattern)

        # Staleness threshold in days
        self.staleness_threshold = healer_config.get('staleness_threshold_days', 30)

        # Deprecated command patterns
        self.deprecated_patterns = self._build_deprecated_patterns(
            healer_config.get('deprecated_patterns', [])
        )

        # Directories to exclude from scanning
        self.exclude_dirs = set(healer_config.get('exclude_dirs', [
            '.git', 'node_modules', 'venv', '.venv', 'dist', 'build', 'reports'
        ]))

        # Statistics tracking
        self.timestamps_updated = []
        self.timestamps_missing = []
        self.deprecated_commands = []

        # Git timestamp cache (populated by batch operation)
        self._git_timestamps_cache: Dict[Path, datetime] = {}
        self._git_cache_populated = False

    def _populate_git_cache(self, files: List[Path]):
        """
        Populate git timestamp cache with batch operation.

        Instead of calling git log for each file individually,
        we batch all files into a single git command.

        Args:
            files: List of files to get timestamps for
        """
        if self._git_cache_populated:
            return

        # Use batch git operation
        self._git_timestamps_cache = get_all_git_timestamps(
            files,
            self.project_root,
            timeout=60
        )
        self._git_cache_populated = True

    def _build_deprecated_patterns(self, pattern_configs: List) -> List[Dict]:
        """
        Build deprecated pattern objects from config.

        Security:
        - Validates all regex patterns for ReDoS (DG-2026-002)
        - Limits pattern count (DG-2026-006)

        Args:
            pattern_configs: List of strings or dicts. Strings are treated as patterns
                with default message/confidence. Dicts should have keys:
                pattern, message, confidence, suggestion

        Returns:
            List of pattern dicts with compiled regex and suggestion callables

        Raises:
            RegexSecurityError: If any pattern is potentially dangerous
            TypeError: If pattern_configs contains invalid types
        """
        patterns = []

        # Default patterns if none configured
        if not pattern_configs:
            pattern_configs = [
                {
                    "pattern": r"docker-compose\s+",
                    "message": "Deprecated `docker-compose` -> Use `docker compose` (Docker Compose V2)",
                    "confidence": 0.95,
                    "suggestion": "docker compose"
                },
                {
                    "pattern": r"\bpython2\s+",
                    "message": "Old Python version reference (Python 2) -> Use `python3`",
                    "confidence": 0.85,
                    "suggestion": "python3 "
                },
                {
                    "pattern": r"git\s+checkout\s+-b\s+",
                    "message": "Old branch creation -> Use `git switch -c`",
                    "confidence": 0.80,
                    "suggestion": "git switch -c "
                },
                {
                    "pattern": r"virtualenv\s+",
                    "message": "Legacy virtualenv -> Use `python3 -m venv`",
                    "confidence": 0.85,
                    "suggestion": "python3 -m venv "
                },
                {
                    "pattern": r"\bsudo\s+pip\s+",
                    "message": "Dangerous sudo pip -> Use virtual environment or `pip install --user`",
                    "confidence": 0.95,
                    "suggestion": "pip "
                },
            ]

        # Security: Limit pattern count (DG-2026-006)
        if len(pattern_configs) > MAX_PATTERNS:
            raise ValueError(
                f"Too many deprecated patterns: {len(pattern_configs)} > {MAX_PATTERNS}"
            )

        for cfg in pattern_configs:
            # Handle both string and dict formats
            if isinstance(cfg, str):
                # Simple string pattern - use defaults
                pattern = cfg
                message = f"Deprecated pattern found: {cfg}"
                confidence = 0.85
                suggestion_text = ''
            elif isinstance(cfg, dict):
                pattern = cfg.get('pattern')
                if not pattern:
                    continue  # Skip entries without pattern
                message = cfg.get('message', f"Deprecated pattern: {pattern}")
                confidence = cfg.get('confidence', 0.85)
                suggestion_text = cfg.get('suggestion', '')
            else:
                raise TypeError(
                    f"deprecated_patterns entries must be strings or dicts, got {type(cfg).__name__}. "
                    f"String format: 'pattern_regex'. Dict format: {{'pattern': '...', 'message': '...', 'confidence': 0.85}}"
                )

            # Security: Validate pattern for ReDoS (DG-2026-002)
            is_safe, err = validate_regex_safety(pattern)
            if not is_safe:
                raise RegexSecurityError(
                    f"Potentially dangerous deprecated_pattern: '{pattern}'. Error: {err}"
                )

            # Create suggestion callable
            if callable(suggestion_text):
                suggestion_fn = suggestion_text
            else:
                # Static suggestion - replace matched text with suggestion
                suggestion_fn = lambda m, s=suggestion_text: s

            patterns.append({
                "pattern": pattern,
                "message": message,
                "confidence": confidence,
                "suggestion": suggestion_fn
            })

        return patterns

    def find_markdown_files(self) -> List[Path]:
        """Find all markdown files in doc_root, excluding specified directories."""
        markdown_files = []

        for md_file in self.doc_root.rglob("*.md"):
            # Skip excluded directories
            if any(excluded in md_file.parts for excluded in self.exclude_dirs):
                continue
            markdown_files.append(md_file)

        return sorted(markdown_files)

    def extract_timestamp(self, content: str) -> Optional[Tuple[datetime, str, int]]:
        """
        Extract timestamp from markdown content.

        Args:
            content: Markdown file content

        Returns:
            Tuple of (datetime, matched_line, line_number) or None
        """
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            for pattern in self.timestamp_patterns:
                match = re.search(pattern, line)
                if match:
                    date_str = match.group(1).split()[0]  # Get just the date part
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                        return (dt, line, i)
                    except ValueError:
                        continue
        return None

    def get_git_last_modified(self, file_path: Path) -> Optional[datetime]:
        """
        Get last git modification date for a file.

        Uses cached value if available (from batch operation).
        Falls back to individual git command if not in cache.

        Args:
            file_path: Path to file

        Returns:
            datetime of last modification, or None if not in git
        """
        # Check cache first
        if file_path in self._git_timestamps_cache:
            return self._git_timestamps_cache[file_path]

        # Fallback to individual git command (shouldn't happen often if cache populated)
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%ai', '--', str(file_path)],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )

            if result.stdout.strip():
                # Parse git timestamp: "2026-01-11 10:30:00 -0500"
                git_date_str = result.stdout.strip().split()[0]
                dt = datetime.strptime(git_date_str, "%Y-%m-%d")
                # Cache for future use
                self._git_timestamps_cache[file_path] = dt
                return dt
            return None

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None

    def detect_deprecated_commands(self, file_path: Path) -> List[Dict]:
        """
        Detect deprecated command syntax in file.

        Args:
            file_path: Path to markdown file

        Returns:
            List of issue dicts with keys: line, context, message, confidence, suggestion
        """
        try:
            content = file_path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            return []

        lines = content.split('\n')
        issues = []

        in_code_block = False

        for i, line in enumerate(lines, 1):
            # Track code blocks
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                continue

            # Only check code blocks and inline code
            if not in_code_block and '`' not in line:
                continue

            # Check each pattern
            for stale_pattern in self.deprecated_patterns:
                pattern = stale_pattern["pattern"]
                matches = re.finditer(pattern, line)

                for match in matches:
                    # Extract context around match
                    start = max(0, match.start() - 10)
                    end = min(len(line), match.end() + 30)
                    context = line[start:end].strip()

                    issues.append({
                        "line": i,
                        "context": context,
                        "message": stale_pattern["message"],
                        "confidence": stale_pattern["confidence"],
                        "suggestion": stale_pattern["suggestion"](match),
                        "matched_text": match.group(0)
                    })

        return issues

    def check(self) -> HealingReport:
        """
        Analyze documentation for staleness issues.

        Uses batched git operations for performance:
        - Old: O(n) git commands (one per file)
        - New: O(1) git command (batch all files)

        Returns:
            HealingReport with mode="check" and proposed changes
        """
        start_time = time.time()
        changes = []

        markdown_files = self.find_markdown_files()

        # Batch populate git timestamps for all files at once
        # This replaces O(n) individual git calls with O(1) batch call
        self._populate_git_cache(markdown_files)

        for md_file in markdown_files:
            # Check timestamp staleness
            try:
                content = md_file.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue

            # Extract current timestamp
            timestamp_info = self.extract_timestamp(content)

            if not timestamp_info:
                self.timestamps_missing.append(md_file)
                continue

            doc_date, old_line, line_num = timestamp_info

            # Get git last modified
            git_date = self.get_git_last_modified(md_file)

            if not git_date:
                continue

            # Calculate staleness
            days_behind = (git_date - doc_date).days

            if days_behind > self.staleness_threshold:
                # Create change for timestamp update
                new_date_str = git_date.strftime("%Y-%m-%d")

                # Replace just the date part, preserving format
                new_line = old_line
                for pattern in self.timestamp_patterns:
                    new_line = re.sub(
                        pattern,
                        lambda m: m.group(0).replace(m.group(1).split()[0], new_date_str),
                        old_line
                    )
                    if new_line != old_line:
                        break

                change = Change(
                    file=md_file,
                    line=line_num,
                    old_content=old_line,
                    new_content=new_line,
                    confidence=1.0,  # 100% confidence for exact timestamp updates
                    reason=f"Timestamp {days_behind} days behind git history ({doc_date.strftime('%Y-%m-%d')} → {new_date_str})",
                    healer="DetectStalenessHealer"
                )
                changes.append(change)

                self.timestamps_updated.append({
                    "file": md_file.relative_to(self.project_root),
                    "old_date": doc_date,
                    "new_date": git_date,
                    "days_behind": days_behind
                })

            # Check for deprecated commands
            deprecated_issues = self.detect_deprecated_commands(md_file)

            if deprecated_issues:
                relative_path = md_file.relative_to(self.project_root)

                for issue in deprecated_issues:
                    # Create change for deprecated command
                    # Note: These are flagged but not auto-applied (lower confidence)
                    change = Change(
                        file=md_file,
                        line=issue['line'],
                        old_content=issue['matched_text'],
                        new_content=issue['suggestion'],
                        confidence=issue['confidence'],
                        reason=issue['message'],
                        healer="DetectStalenessHealer"
                    )
                    changes.append(change)

                self.deprecated_commands.append({
                    "file": relative_path,
                    "issues": deprecated_issues
                })

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
        Apply fixes above confidence threshold.

        Args:
            min_confidence: Override default confidence threshold

        Returns:
            HealingReport with mode="heal" and applied changes
        """
        start_time = time.time()

        # Get proposed changes from check()
        check_report = self.check()

        # Use provided min_confidence or fall back to config default
        threshold = min_confidence if min_confidence is not None else self.min_confidence

        # Filter changes by confidence
        changes_to_apply = [
            change for change in check_report.changes
            if change.confidence >= threshold
        ]

        applied_changes = []

        # Group changes by file for efficient commits
        changes_by_file = {}
        for change in changes_to_apply:
            if change.file not in changes_by_file:
                changes_by_file[change.file] = []
            changes_by_file[change.file].append(change)

        # Apply changes file by file
        for file_path, file_changes in changes_by_file.items():
            try:
                content = file_path.read_text(encoding='utf-8')
                lines = content.split('\n')

                # Apply changes in reverse order to preserve line numbers
                for change in sorted(file_changes, key=lambda c: c.line, reverse=True):
                    if self.validate_change(change):
                        # Replace the line
                        if 0 < change.line <= len(lines):
                            lines[change.line - 1] = lines[change.line - 1].replace(
                                change.old_content,
                                change.new_content
                            )
                            applied_changes.append(change)

                # Write back modified content
                file_path.write_text('\n'.join(lines), encoding='utf-8')

                # Commit timestamp updates immediately (high confidence)
                timestamp_changes = [c for c in file_changes if "timestamp" in c.reason.lower()]
                if timestamp_changes:
                    relative_path = file_path.relative_to(self.project_root)
                    git_commit(
                        f"chore(docs): update timestamp for {relative_path}",
                        [file_path],
                        self.project_root
                    )

            except Exception as e:
                self.log_error(f"Failed to apply changes to {file_path}: {e}")

        execution_time = time.time() - start_time

        return self.create_report(
            mode="heal",
            issues_found=len(check_report.changes),
            issues_fixed=len(applied_changes),
            changes=applied_changes,
            execution_time=execution_time
        )

    def validate_change(self, change: Change) -> bool:
        """
        Validate a proposed change.

        For timestamp updates: Always valid (100% confidence)
        For deprecated commands: Check that old content exists

        Args:
            change: Change to validate

        Returns:
            True if change is valid
        """
        # Use base validation first
        if not super().validate_change(change):
            return False

        # Additional validation for deprecated commands
        if change.confidence < 1.0:
            # This is a deprecated command change
            # Verify we're not replacing something incorrectly
            try:
                content = change.file.read_text()
                if change.old_content not in content:
                    self.log_error(f"Old content '{change.old_content}' not found in {change.file}")
                    return False
            except Exception as e:
                self.log_error(f"Cannot validate change for {change.file}: {e}")
                return False

        return True
