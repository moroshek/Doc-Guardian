"""
Progressive Disclosure Enforcer

Prevents detail creep from violating documentation layer hierarchy.

Enforcement rules (configurable):
1. Size limits per layer (e.g., no sections >50 lines in overview)
2. Depth limits per layer (e.g., max heading depth)
3. Jargon detection in overview layers
4. Detail indicators (code blocks, step-by-step, API docs)

Configuration keys:
    healers.enforce_disclosure.layer_definitions: Layer-to-file mappings and limits
    healers.enforce_disclosure.jargon_patterns: Technical terms to flag in overview
    healers.enforce_disclosure.detail_indicators: Patterns indicating too much detail
    healers.enforce_disclosure.keyword_mappings: Section title to target file mappings

Example config:
    {
        "healers": {
            "enforce_disclosure": {
                "layer_definitions": {
                    "overview": {
                        "max_lines": 50,
                        "allowed_depth": 2,
                        "files": ["README.md", "*/index.md"]
                    },
                    "guide": {
                        "max_lines": 200,
                        "allowed_depth": 3,
                        "files": ["docs/guides/*.md"]
                    }
                },
                "jargon_patterns": ["memgraph", "embeddings", "vector database"],
                "detail_indicators": [
                    {"pattern": "```(?:python|bash).{200,}```", "description": "Long code examples"},
                    {"pattern": "Step \\d+:", "description": "Step-by-step instructions"}
                ],
                "keyword_mappings": {
                    "search": "docs/domains/search.md",
                    "deploy": "docs/deployment.md"
                }
            }
        }
    }
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from fnmatch import fnmatch
import time

from ..core.base import HealingSystem, HealingReport, Change


@dataclass
class Section:
    """A markdown section with location and content metadata."""
    file: Path
    title: str
    level: int  # 1 for #, 2 for ##, etc.
    start_line: int
    end_line: int
    content: str
    line_count: int


@dataclass
class LayerDefinition:
    """Definition of a documentation layer."""
    name: str
    max_lines: int
    allowed_depth: int
    file_patterns: List[str]


class SectionExtractor:
    """Extract sections from markdown files."""

    HEADER_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$')

    def extract_sections(self, file_path: Path) -> List[Section]:
        """
        Extract all sections from a markdown file.

        Args:
            file_path: Path to markdown file

        Returns:
            List of Section objects with metadata
        """
        sections = []

        try:
            with open(file_path) as f:
                lines = f.readlines()

            current_section = None
            section_lines = []

            for i, line in enumerate(lines, 1):
                header_match = self.HEADER_PATTERN.match(line.strip())

                if header_match:
                    # Save previous section
                    if current_section:
                        sections.append(Section(
                            file=file_path,
                            title=current_section['title'],
                            level=current_section['level'],
                            start_line=current_section['start'],
                            end_line=i-1,
                            content=''.join(section_lines),
                            line_count=len(section_lines)
                        ))

                    # Start new section
                    level = len(header_match.group(1))
                    title = header_match.group(2)
                    current_section = {
                        'title': title,
                        'level': level,
                        'start': i
                    }
                    section_lines = []
                else:
                    if current_section:
                        section_lines.append(line)

            # Save last section
            if current_section:
                sections.append(Section(
                    file=file_path,
                    title=current_section['title'],
                    level=current_section['level'],
                    start_line=current_section['start'],
                    end_line=len(lines),
                    content=''.join(section_lines),
                    line_count=len(section_lines)
                ))

        except Exception as e:
            # Don't raise - just return empty list
            pass

        return sections


class EnforceDisclosureHealer(HealingSystem):
    """
    Healing system for enforcing progressive disclosure.

    Checks documentation layers for:
    - Oversized sections
    - Excessive heading depth
    - Technical jargon in overview layers
    - Detail creep (code blocks, step-by-step, API docs)

    Proposes changes with confidence scores:
    - 85% confidence: Clear size violation with known target
    - 65% confidence: Jargon or detail creep with unclear layer
    - <65% confidence: Manual review needed
    """

    def __init__(self, config: Dict):
        """
        Initialize healer with configuration.

        Args:
            config: Full configuration dict with healers.enforce_disclosure section
        """
        super().__init__(config)

        # Extract healer-specific config
        healer_config = config.get('healers', {}).get('enforce_disclosure', {})

        # Load layer definitions
        self.layers = self._load_layer_definitions(healer_config.get('layer_definitions', {}))

        # Load jargon patterns (compiled regexes)
        self.jargon_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in healer_config.get('jargon_patterns', [])
        ]

        # Load detail indicators
        self.detail_indicators = [
            (re.compile(item['pattern'], re.DOTALL), item['description'])
            for item in healer_config.get('detail_indicators', [])
        ]

        # Load keyword mappings (section title keywords to target files)
        self.keyword_mappings = healer_config.get('keyword_mappings', {})

        # Section extractor
        self.extractor = SectionExtractor()

    def _load_layer_definitions(self, layer_config: Dict) -> List[LayerDefinition]:
        """
        Parse layer definitions from config.

        Args:
            layer_config: Dict mapping layer names to configuration

        Returns:
            List of LayerDefinition objects
        """
        layers = []
        for name, settings in layer_config.items():
            layers.append(LayerDefinition(
                name=name,
                max_lines=settings.get('max_lines', 1000),
                allowed_depth=settings.get('allowed_depth', 5),
                file_patterns=settings.get('files', [])
            ))
        return layers

    def check(self) -> HealingReport:
        """
        Analyze documentation for progressive disclosure violations.

        Returns:
            HealingReport with mode="check" and proposed changes
        """
        start_time = time.time()
        changes: List[Change] = []

        # Find all files matching layer patterns
        for layer in self.layers:
            for pattern in layer.file_patterns:
                for file_path in self._glob_files(pattern):
                    if not file_path.exists():
                        continue

                    sections = self.extractor.extract_sections(file_path)

                    # Check oversized sections
                    changes.extend(self._check_oversized_sections(sections, layer))

                    # Check depth violations
                    changes.extend(self._check_depth_violations(sections, layer))

                    # Check jargon (only in overview layers)
                    if layer.name == 'overview':
                        changes.extend(self._check_jargon(sections))

                    # Check detail creep
                    changes.extend(self._check_detail_creep(sections))

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

        # Get proposed changes
        check_report = self.check()

        # Use provided threshold or default
        threshold = min_confidence if min_confidence is not None else self.min_confidence

        # Filter by confidence
        high_confidence_changes = [
            c for c in check_report.changes
            if c.confidence >= threshold
        ]

        applied_changes = []
        for change in high_confidence_changes:
            if self.validate_change(change):
                if self._apply_disclosure_change(change):
                    applied_changes.append(change)

        execution_time = time.time() - start_time

        return self.create_report(
            mode="heal",
            issues_found=len(check_report.changes),
            issues_fixed=len(applied_changes),
            changes=applied_changes,
            execution_time=execution_time
        )

    def _glob_files(self, pattern: str) -> List[Path]:
        """
        Find files matching glob pattern.

        Args:
            pattern: Glob pattern (e.g., "*.md", "docs/**/*.md")

        Returns:
            List of matching file paths
        """
        # Handle patterns with wildcards
        if '*' in pattern:
            # Use pathlib glob
            matches = list(self.doc_root.glob(pattern))
            # Also check project root for README.md etc.
            matches.extend(list(self.project_root.glob(pattern)))
            return matches
        else:
            # Direct path
            absolute_path = self.project_root / pattern
            return [absolute_path] if absolute_path.exists() else []

    def _check_oversized_sections(
        self,
        sections: List[Section],
        layer: LayerDefinition
    ) -> List[Change]:
        """
        Check for sections exceeding layer's max line count.

        Args:
            sections: List of sections from a file
            layer: Layer definition with max_lines limit

        Returns:
            List of Change objects for oversized sections
        """
        changes = []

        for section in sections:
            if section.line_count > layer.max_lines:
                # Suggest target file based on section title
                suggested_file = self._suggest_target_file(section.title)

                # High confidence if we have a clear target
                confidence = 0.85 if suggested_file else 0.65

                changes.append(Change(
                    file=section.file,
                    line=section.start_line,
                    old_content=self._extract_section_text(section),
                    new_content=self._create_section_link(section, suggested_file),
                    confidence=confidence,
                    reason=f"Section '{section.title}' has {section.line_count} lines (max {layer.max_lines} for {layer.name} layer)",
                    healer="EnforceDisclosureHealer"
                ))

        return changes

    def _check_depth_violations(
        self,
        sections: List[Section],
        layer: LayerDefinition
    ) -> List[Change]:
        """
        Check for sections with excessive heading depth.

        Args:
            sections: List of sections from a file
            layer: Layer definition with allowed_depth limit

        Returns:
            List of Change objects for depth violations
        """
        changes = []

        for section in sections:
            if section.level > layer.allowed_depth:
                suggested_file = self._suggest_target_file(section.title)
                confidence = 0.75 if suggested_file else 0.60

                changes.append(Change(
                    file=section.file,
                    line=section.start_line,
                    old_content=self._extract_section_text(section),
                    new_content=self._create_section_link(section, suggested_file),
                    confidence=confidence,
                    reason=f"Section '{section.title}' has depth {section.level} (max {layer.allowed_depth} for {layer.name} layer)",
                    healer="EnforceDisclosureHealer"
                ))

        return changes

    def _check_jargon(self, sections: List[Section]) -> List[Change]:
        """
        Check for technical jargon in overview sections.

        Args:
            sections: List of sections to check

        Returns:
            List of Change objects for jargon violations
        """
        changes = []

        for section in sections:
            # Only check sections with "quick" or "overview" in title
            title_lower = section.title.lower()
            if not any(keyword in title_lower for keyword in ['quick', 'overview', 'start', 'introduction']):
                continue

            # Check for jargon patterns
            for pattern in self.jargon_patterns:
                if pattern.search(section.content):
                    match_text = pattern.search(section.content).group(0)

                    changes.append(Change(
                        file=section.file,
                        line=section.start_line,
                        old_content=self._extract_section_text(section),
                        new_content="",  # Placeholder - manual review needed
                        confidence=0.65,
                        reason=f"Overview section '{section.title}' contains technical term '{match_text}' (should be in detail layer)",
                        healer="EnforceDisclosureHealer"
                    ))
                    break  # One violation per section

        return changes

    def _check_detail_creep(self, sections: List[Section]) -> List[Change]:
        """
        Check for inappropriate detail level in sections.

        Args:
            sections: List of sections to check

        Returns:
            List of Change objects for detail violations
        """
        changes = []

        for section in sections:
            for pattern, description in self.detail_indicators:
                if pattern.search(section.content):
                    suggested_file = self._suggest_target_file(section.title)
                    confidence = 0.70 if suggested_file else 0.60

                    changes.append(Change(
                        file=section.file,
                        line=section.start_line,
                        old_content=self._extract_section_text(section),
                        new_content=self._create_section_link(section, suggested_file),
                        confidence=confidence,
                        reason=f"Section '{section.title}' contains {description} (belongs in detail layer)",
                        healer="EnforceDisclosureHealer"
                    ))
                    break  # One violation per section

        return changes

    def _suggest_target_file(self, section_title: str) -> Optional[Path]:
        """
        Suggest target file based on section title keywords.

        Args:
            section_title: Title of section to move

        Returns:
            Path to suggested target file, or None if unclear
        """
        title_lower = section_title.lower()

        for keyword, target_file in self.keyword_mappings.items():
            if keyword in title_lower:
                return self.project_root / target_file

        return None

    def _extract_section_text(self, section: Section) -> str:
        """
        Extract full section text including header.

        Args:
            section: Section object

        Returns:
            Full section text as string
        """
        try:
            with open(section.file) as f:
                lines = f.readlines()

            # Include header line + content
            return ''.join(lines[section.start_line-1:section.end_line])

        except Exception as e:
            self.log_error(f"Failed to extract section text from {section.file}: {e}")
            return ""

    def _create_section_link(self, section: Section, target_file: Optional[Path]) -> str:
        """
        Create a link to replace section content.

        Args:
            section: Section to replace
            target_file: Target file to link to (or None for manual review)

        Returns:
            Markdown link text
        """
        header_prefix = '#' * section.level

        if target_file:
            # Get relative path from source to target
            try:
                rel_path = target_file.relative_to(section.file.parent)
            except ValueError:
                # Files in different trees - use absolute path from project root
                rel_path = '/' + str(target_file.relative_to(self.project_root))

            return f"\n\n{header_prefix} {section.title}\n\nSee [{target_file.name}]({rel_path})\n\n"
        else:
            # No target - flag for manual review
            return f"\n\n{header_prefix} {section.title}\n\n<!-- TODO: Move to appropriate detail layer -->\n\n"

    def _apply_disclosure_change(self, change: Change) -> bool:
        """
        Apply a progressive disclosure change.

        This extends the base apply_change with:
        1. Move section content to target file (if specified)
        2. Replace with link in source file
        3. Ensure target file exists

        Args:
            change: Change object to apply

        Returns:
            True if change was successfully applied
        """
        try:
            # Read source file
            source_content = change.file.read_text()

            # If new_content is just a link, extract target file
            # and append section content there
            if "See [" in change.new_content and "](" in change.new_content:
                # Extract target file from link
                link_match = re.search(r'\[(.+?)\]\((.+?)\)', change.new_content)
                if link_match:
                    target_path_str = link_match.group(2)

                    # Resolve target path
                    if target_path_str.startswith('/'):
                        target_file = self.project_root / target_path_str.lstrip('/')
                    else:
                        target_file = change.file.parent / target_path_str

                    # Create target file if doesn't exist
                    if not target_file.exists():
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        target_file.touch()

                    # Append section content to target
                    with open(target_file, 'a') as f:
                        f.write(f"\n\n{change.old_content}")

            # Replace in source file
            new_source = source_content.replace(change.old_content, change.new_content)
            change.file.write_text(new_source)

            return True

        except Exception as e:
            self.log_error(f"Failed to apply disclosure change to {change.file}: {e}")
            return False
