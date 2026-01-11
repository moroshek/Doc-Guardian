"""
Cross-Reference Balance Healer

Ensures bidirectional links between related documentation files.

Example:
- If api.md links to guide.md
- Then guide.md should link back to api.md

This healer:
1. Builds a directed graph of all documentation links
2. Detects missing backlinks (A→B exists but B→A doesn't)
3. Adds backlinks with configurable format and confidence scoring
4. Validates graph consistency

Security features:
- ReDoS protection for user-provided regex patterns (DG-2026-002)
- File size limits (DG-2026-006)
- Pattern count limits (DG-2026-006)

Configuration:
    config['healers']['balance_references']:
        reference_patterns: List of regex patterns for link detection
        backlink_format: Template for adding backlinks (supports {title}, {path})
        related_section_headers: List of section headers to look for
        min_confidence: Minimum confidence for auto-adding backlinks
        exclude_paths: List of path patterns to exclude from analysis
"""

import re
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Tuple

from ..core.base import HealingSystem, HealingReport, Change
from ..core.regex_validator import (
    validate_regex_safety,
    RegexSecurityError,
)
from ..core.security import (
    validate_file_size,
    safe_read_file,
    MAX_PATTERNS,
    MAX_LINKS_PER_FILE,
)


@dataclass
class Link:
    """
    A markdown link from one file to another.

    Attributes:
        source: Path to file containing the link
        target: Path to file being linked to
        text: Link text (the part in square brackets)
        line_num: Line number where link appears
    """
    source: Path
    target: Path
    text: str
    line_num: int


@dataclass
class MissingBacklink:
    """
    A missing bidirectional link.

    Attributes:
        forward_link: The existing A→B link
        suggested_backlink: The missing B→A backlink
        confidence: Confidence score (0.0-1.0) for adding this backlink
    """
    forward_link: Link
    suggested_backlink: Link
    confidence: float


class LinkGraphBuilder:
    """
    Build a directed graph of documentation links.

    Extracts links from markdown files and resolves relative paths
    to create a comprehensive link graph.
    """

    def __init__(
        self,
        project_root: Path,
        link_patterns: Optional[List[str]] = None
    ):
        """
        Initialize graph builder.

        Security:
        - Validates all regex patterns for ReDoS (DG-2026-002)
        - Limits pattern count (DG-2026-006)

        Args:
            project_root: Root directory of the project
            link_patterns: Regex patterns for link detection
                          Default: standard markdown link pattern

        Raises:
            RegexSecurityError: If any pattern is potentially dangerous
        """
        self.project_root = project_root

        # Default to standard markdown link pattern
        if link_patterns is None:
            link_patterns = [r'\[([^\]]+)\]\(([^\)]+)\)']

        # Security: Limit pattern count (DG-2026-006)
        if len(link_patterns) > MAX_PATTERNS:
            raise ValueError(
                f"Too many link patterns: {len(link_patterns)} > {MAX_PATTERNS}"
            )

        # Security: Validate patterns for ReDoS (DG-2026-002)
        self.link_patterns = []
        for pattern in link_patterns:
            is_safe, error = validate_regex_safety(pattern)
            if not is_safe:
                raise RegexSecurityError(
                    f"Potentially dangerous link pattern: '{pattern}'. Error: {error}"
                )
            self.link_patterns.append(re.compile(pattern))

    def extract_links(self, file_path: Path) -> List[Link]:
        """
        Extract all links from a file.

        Security:
        - File size validation before reading (DG-2026-006)
        - Link count limit per file (DG-2026-006)

        Args:
            file_path: Path to markdown file

        Returns:
            List of Link objects found in the file
        """
        links = []

        try:
            # Security: Validate file size before reading (DG-2026-006)
            is_valid, error = validate_file_size(file_path)
            if not is_valid:
                return links

            with open(file_path) as f:
                for line_num, line in enumerate(f, 1):
                    for pattern in self.link_patterns:
                        for match in pattern.finditer(line):
                            # Security: Limit links per file (DG-2026-006)
                            if len(links) >= MAX_LINKS_PER_FILE:
                                return links

                            text, target = match.groups()

                            # Skip external links
                            if target.startswith(('http://', 'https://', 'mailto:')):
                                continue

                            # Skip anchor-only links
                            if target.startswith('#'):
                                continue

                            # Resolve target path
                            target_path = self._resolve_path(file_path, target)
                            if target_path:
                                links.append(Link(
                                    source=file_path,
                                    target=target_path,
                                    text=text,
                                    line_num=line_num
                                ))

        except Exception as e:
            # Silently skip files that can't be read
            pass

        return links

    def _resolve_path(self, source: Path, target: str) -> Optional[Path]:
        """
        Resolve target path relative to source file.

        Args:
            source: Path to file containing the link
            target: Link target (may be relative or absolute)

        Returns:
            Absolute Path if target exists, None otherwise
        """
        # Strip anchor
        if '#' in target:
            target = target.split('#')[0]

        if not target:
            return None

        # Absolute path (project-relative)
        if target.startswith('/'):
            abs_path = self.project_root / target.lstrip('/')
        else:
            # Relative path
            abs_path = (source.parent / target).resolve()

        return abs_path if abs_path.exists() else None

    def build_graph(self, files: List[Path]) -> Dict[Path, List[Link]]:
        """
        Build link graph from list of files.

        Args:
            files: List of file paths to analyze

        Returns:
            Dict mapping each file to its outgoing links
        """
        graph = {}

        for file_path in files:
            links = self.extract_links(file_path)
            graph[file_path] = links

        return graph


class BacklinkChecker:
    """
    Check for missing backlinks in a link graph.

    For each link A→B, verifies that B→A exists. If not,
    suggests adding the backlink with a confidence score.
    """

    def check_backlinks(
        self,
        graph: Dict[Path, List[Link]]
    ) -> List[MissingBacklink]:
        """
        Find all missing backlinks in the graph.

        Args:
            graph: Dict mapping files to outgoing links

        Returns:
            List of MissingBacklink objects
        """
        missing = []

        for source, outgoing_links in graph.items():
            for link in outgoing_links:
                target = link.target

                # Check if target has backlink to source
                if target in graph:
                    target_links = graph[target]
                    has_backlink = any(tl.target == source for tl in target_links)

                    if not has_backlink:
                        # Suggest backlink
                        suggested = Link(
                            source=target,
                            target=source,
                            text=source.stem,  # Use filename without extension
                            line_num=0  # Will be determined during insertion
                        )

                        # Calculate confidence
                        confidence = self._calculate_confidence(link, suggested, graph)

                        missing.append(MissingBacklink(
                            forward_link=link,
                            suggested_backlink=suggested,
                            confidence=confidence
                        ))

        return missing

    def _calculate_confidence(
        self,
        forward: Link,
        backward: Link,
        graph: Dict[Path, List[Link]]
    ) -> float:
        """
        Calculate confidence score for adding a backlink.

        Higher confidence when:
        - Files are in the same directory (related docs)
        - Files are at similar hierarchy levels
        - Both files have multiple mutual links

        Args:
            forward: The existing A→B link
            backward: The proposed B→A backlink
            graph: Full link graph for context

        Returns:
            Confidence score (0.0-1.0)
        """
        confidence = 0.70  # Base confidence

        # Same directory = related docs
        if forward.source.parent == backward.source.parent:
            confidence += 0.20

        # Similar hierarchy depth
        source_depth = len(forward.source.parts)
        target_depth = len(backward.source.parts)
        if abs(source_depth - target_depth) <= 1:
            confidence += 0.05

        # Multiple mutual links = stronger relationship
        forward_count = sum(
            1 for link in graph.get(forward.source, [])
            if link.target == forward.target
        )
        if forward_count > 1:
            confidence += 0.05

        return min(confidence, 1.0)


class BacklinkAdder:
    """
    Add missing backlinks to documentation files.

    Inserts backlinks in an appropriate location (preferably
    in a "Related" or "See Also" section).
    """

    def __init__(
        self,
        project_root: Path,
        backlink_format: str = "- [{title}]({path})\n",
        related_headers: Optional[List[str]] = None
    ):
        """
        Initialize backlink adder.

        Args:
            project_root: Project root for path resolution
            backlink_format: Format template for backlinks
                           Supports: {title}, {path}, {filename}
            related_headers: Section headers to look for when adding links
                           Default: ["Related", "See Also", "Navigation"]
        """
        self.project_root = project_root
        self.backlink_format = backlink_format

        if related_headers is None:
            related_headers = ["Related", "See Also", "Navigation"]

        self.related_headers = related_headers

    def add_backlink(self, missing: MissingBacklink) -> bool:
        """
        Add a backlink to the target file.

        Args:
            missing: MissingBacklink object describing what to add

        Returns:
            True if backlink was successfully added
        """
        target_file = missing.suggested_backlink.source

        try:
            with open(target_file) as f:
                content = f.read()

            # Check if link already exists (might be formatted differently)
            target_name = missing.suggested_backlink.target.name
            if target_name in content:
                # Link might already exist in different format
                return False

            # Generate backlink
            rel_path = self._get_relative_path(
                target_file,
                missing.suggested_backlink.target
            )

            backlink = self.backlink_format.format(
                title=missing.suggested_backlink.text,
                path=rel_path,
                filename=missing.suggested_backlink.target.name
            )

            # Find or create related section
            new_content = self._insert_backlink(content, backlink)

            # Write back if changed
            if new_content != content:
                with open(target_file, 'w') as f:
                    f.write(new_content)
                return True

            return False

        except Exception as e:
            # Silently fail - error will be logged by caller
            return False

    def _insert_backlink(self, content: str, backlink: str) -> str:
        """
        Insert backlink into content at appropriate location.

        Prefers existing "Related" sections, creates one if needed.

        Args:
            content: File content
            backlink: Formatted backlink to insert

        Returns:
            Modified content with backlink inserted
        """
        # Look for existing related section
        for header in self.related_headers:
            # Pattern: ## Header (with optional content)
            pattern = rf'(##\s+{header}\s*\n)(.*?)(?=\n##|\Z)'
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

            if match:
                # Insert backlink into existing section
                section_header = match.group(1)
                section_content = match.group(2)

                # Add backlink at start of section (after header)
                new_section = section_header + "\n" + backlink + section_content
                return content[:match.start()] + new_section + content[match.end():]

        # No related section found - add at end
        if not content.endswith('\n'):
            content += '\n'

        return content + f"\n## Related\n\n{backlink}"

    def _get_relative_path(self, from_file: Path, to_file: Path) -> str:
        """
        Get relative path from one file to another.

        Args:
            from_file: Source file
            to_file: Target file

        Returns:
            Relative path string
        """
        try:
            # Try relative path first
            return str(to_file.relative_to(from_file.parent))
        except ValueError:
            # Files not in same tree - use absolute from project root
            try:
                return '/' + str(to_file.relative_to(self.project_root))
            except ValueError:
                # Fallback to absolute path
                return str(to_file)


class BalanceReferencesHealer(HealingSystem):
    """
    Cross-reference balance healer.

    Ensures bidirectional links between related documentation files.

    Configuration:
        config['healers']['balance_references']:
            reference_patterns: List of regex patterns for link detection
            backlink_format: Template for adding backlinks
            related_section_headers: List of headers for related sections
            min_confidence: Minimum confidence for auto-adding
            exclude_paths: List of path patterns to exclude
            doc_globs: List of glob patterns for finding docs
    """

    def __init__(self, config: Dict):
        """Initialize healer with configuration."""
        super().__init__(config)

        # Get healer-specific config
        healer_config = config.get('healers', {}).get('balance_references', {})

        # Link patterns
        self.link_patterns = healer_config.get(
            'reference_patterns',
            [r'\[([^\]]+)\]\(([^\)]+)\)']
        )

        # Backlink format
        self.backlink_format = healer_config.get(
            'backlink_format',
            "- [{title}]({path})\n"
        )

        # Related section headers
        self.related_headers = healer_config.get(
            'related_section_headers',
            ["Related", "See Also", "Navigation"]
        )

        # Exclusions
        self.exclude_patterns = healer_config.get('exclude_paths', [])

        # Doc file globs
        self.doc_globs = healer_config.get(
            'doc_globs',
            ['**/*.md']
        )

        # Initialize components
        self.graph_builder = LinkGraphBuilder(
            self.project_root,
            self.link_patterns
        )
        self.backlink_checker = BacklinkChecker()
        self.backlink_adder = BacklinkAdder(
            self.project_root,
            self.backlink_format,
            self.related_headers
        )

    def check(self) -> HealingReport:
        """
        Check all documentation for missing backlinks.

        Returns:
            HealingReport with mode="check" and list of missing backlinks
        """
        start_time = time.time()

        # Find all documentation files
        doc_files = self._get_doc_files()

        # Build link graph
        graph = self.graph_builder.build_graph(doc_files)

        # Find missing backlinks
        missing = self.backlink_checker.check_backlinks(graph)

        # Convert to Change objects
        changes = []
        for m in missing:
            changes.append(Change(
                file=m.suggested_backlink.source,
                line=0,  # Will be inserted at appropriate location
                old_content="",  # Adding new content
                new_content=self._format_backlink(m.suggested_backlink),
                confidence=m.confidence,
                reason=f"Missing backlink to {m.suggested_backlink.target.name} (referenced by {m.forward_link.source.name})",
                healer="BalanceReferencesHealer"
            ))

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
        Add missing backlinks above confidence threshold.

        Args:
            min_confidence: Override default confidence threshold

        Returns:
            HealingReport with mode="heal" and list of applied changes
        """
        start_time = time.time()

        # Get proposed changes
        check_report = self.check()

        # Apply threshold
        threshold = min_confidence if min_confidence is not None else self.min_confidence

        # Track results
        applied_changes = []
        issues_fixed = 0

        for change in check_report.changes:
            if change.confidence >= threshold:
                # Reconstruct MissingBacklink for backlink_adder
                # (We need this because Change doesn't preserve all metadata)
                missing = MissingBacklink(
                    forward_link=Link(
                        source=Path("unknown"),  # Not needed for add operation
                        target=change.file,
                        text="",
                        line_num=0
                    ),
                    suggested_backlink=Link(
                        source=change.file,
                        target=self._extract_target_from_change(change),
                        text=self._extract_title_from_change(change),
                        line_num=0
                    ),
                    confidence=change.confidence
                )

                # Validate and apply
                if self.backlink_adder.add_backlink(missing):
                    applied_changes.append(change)
                    issues_fixed += 1
                else:
                    self.log_error(f"Failed to add backlink to {change.file}")

        execution_time = time.time() - start_time

        return self.create_report(
            mode="heal",
            issues_found=len(check_report.changes),
            issues_fixed=issues_fixed,
            changes=applied_changes,
            execution_time=execution_time
        )

    def _get_doc_files(self) -> List[Path]:
        """
        Get list of documentation files to analyze.

        Returns:
            List of Path objects for markdown files
        """
        files = []

        for glob_pattern in self.doc_globs:
            for file_path in self.doc_root.glob(glob_pattern):
                # Skip excluded paths
                if self._is_excluded(file_path):
                    continue

                if file_path.is_file():
                    files.append(file_path)

        return files

    def _is_excluded(self, file_path: Path) -> bool:
        """
        Check if file path matches exclusion patterns.

        Args:
            file_path: Path to check

        Returns:
            True if file should be excluded
        """
        for pattern in self.exclude_patterns:
            if re.search(pattern, str(file_path)):
                return True
        return False

    def _format_backlink(self, link: Link) -> str:
        """
        Format a backlink using configured template.

        Args:
            link: Link object to format

        Returns:
            Formatted backlink string
        """
        rel_path = self.backlink_adder._get_relative_path(link.source, link.target)

        return self.backlink_format.format(
            title=link.text,
            path=rel_path,
            filename=link.target.name
        )

    def _extract_target_from_change(self, change: Change) -> Path:
        """
        Extract target path from Change.new_content.

        This is a helper for reconstructing Link objects from Change objects.

        Args:
            change: Change object

        Returns:
            Path to target file
        """
        # Parse link from new_content
        match = re.search(r'\]\(([^\)]+)\)', change.new_content)
        if match:
            target_str = match.group(1)
            # Resolve path
            if target_str.startswith('/'):
                return self.project_root / target_str.lstrip('/')
            else:
                return (change.file.parent / target_str).resolve()

        # Fallback: extract from reason
        # "Missing backlink to filename.md (referenced by ...)"
        match = re.search(r'Missing backlink to (\S+)', change.reason)
        if match:
            filename = match.group(1)
            # Search for file with this name
            for file_path in self.doc_root.rglob(filename):
                return file_path

        # Last resort: return change.file
        return change.file

    def _extract_title_from_change(self, change: Change) -> str:
        """
        Extract link title from Change.new_content.

        Args:
            change: Change object

        Returns:
            Link title
        """
        # Parse link from new_content
        match = re.search(r'\[([^\]]+)\]', change.new_content)
        if match:
            return match.group(1)

        # Fallback to filename
        return change.file.stem
