"""
Collapsed Section Manager - Universal Healer

Manages collapsible <details> sections in documentation:
1. Maintains search index keywords
2. Generates expand hints from content
3. Detects stale/never-used sections
4. Archives unused content with user approval

This healer is configurable and project-agnostic.
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Any
from collections import Counter
import time

from ..core.base import HealingSystem, HealingReport, Change


@dataclass
class CollapsedSection:
    """A collapsible section found in documentation."""
    file: Path
    title: str
    summary: str  # The <summary> text
    content: str
    start_line: int
    end_line: int
    keywords: Set[str]  # Keywords extracted from content


class CollapsedSectionExtractor:
    """Extract collapsible <details> sections from markdown."""

    DETAILS_PATTERN = re.compile(
        r'<details>\s*<summary>(.+?)</summary>\s*(.+?)\s*</details>',
        re.DOTALL
    )

    def __init__(self, stopwords: Optional[Set[str]] = None):
        """
        Initialize extractor.

        Args:
            stopwords: Words to exclude from keyword extraction.
                      Uses default set if None.
        """
        self.stopwords = stopwords or {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all',
            'can', 'has', 'had', 'was', 'will', 'this', 'that', 'with', 'from'
        }

    def extract(self, file_path: Path) -> List[CollapsedSection]:
        """
        Extract all collapsed sections from a file.

        Args:
            file_path: Path to markdown file

        Returns:
            List of CollapsedSection objects
        """
        sections = []

        try:
            content = file_path.read_text()

            for match in self.DETAILS_PATTERN.finditer(content):
                summary = match.group(1).strip()
                section_content = match.group(2).strip()

                # Extract keywords from content
                keywords = self._extract_keywords(section_content)

                # Calculate line numbers
                start_pos = match.start()
                start_line = content[:start_pos].count('\n') + 1
                end_line = content[:match.end()].count('\n') + 1

                sections.append(CollapsedSection(
                    file=file_path,
                    title=summary,
                    summary=summary,
                    content=section_content,
                    start_line=start_line,
                    end_line=end_line,
                    keywords=keywords
                ))

        except Exception as e:
            # Silently skip - errors will be logged by caller
            pass

        return sections

    def _extract_keywords(self, content: str) -> Set[str]:
        """
        Extract keywords from content.

        Args:
            content: Section content

        Returns:
            Set of keywords (lowercase, 3+ chars, no stopwords)
        """
        # Remove markdown formatting
        text = re.sub(r'[#*`\[\]()]', ' ', content)

        # Extract words (3+ chars)
        words = re.findall(r'\b\w{3,}\b', text.lower())

        # Filter stopwords
        keywords = {w for w in words if w not in self.stopwords}

        return keywords


class SearchIndexChecker:
    """Check if search index contains keywords from collapsed sections."""

    def check_index(
        self,
        sections: List[CollapsedSection],
        index_content: str,
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Check if search index contains keywords from collapsed sections.

        Args:
            sections: List of CollapsedSection objects
            index_content: Search index content (or entire doc if no dedicated index)
            threshold: Ratio of missing keywords to total that triggers issue (default 0.5)

        Returns:
            List of issue dicts with keys: section, issue_type, description, suggested_fix, confidence
        """
        issues = []

        # Extract keywords from index
        index_keywords = set(re.findall(r'\b\w{3,}\b', index_content.lower()))

        for section in sections:
            # Key terms that MUST be in index
            missing = section.keywords - index_keywords

            # If > threshold of keywords missing, flag it
            if section.keywords and len(missing) > len(section.keywords) * threshold:
                issues.append({
                    'section': section,
                    'issue_type': 'missing_keywords',
                    'description': f"Section '{section.title}' has {len(missing)} keywords not in search index",
                    'suggested_fix': f"Add to index: {', '.join(list(missing)[:5])}",
                    'confidence': 0.8
                })

        return issues


class ExpandHintGenerator:
    """Generate expand hints from section content."""

    def __init__(self, strategy: str = 'first_sentence'):
        """
        Initialize hint generator.

        Args:
            strategy: Hint generation strategy:
                     - 'first_sentence': Use first sentence of content
                     - 'keywords': Use most common keywords
                     - 'summary': Count code blocks/commands/bullets
        """
        self.strategy = strategy

    def generate_hint(self, section: CollapsedSection) -> str:
        """
        Generate an expand hint that describes what's inside.

        Good hint: "Expand to see: 15 command examples with flags"
        Bad hint: "Click to expand"

        Args:
            section: CollapsedSection object

        Returns:
            Hint string
        """
        if self.strategy == 'first_sentence':
            return self._first_sentence_hint(section)
        elif self.strategy == 'keywords':
            return self._keywords_hint(section)
        else:  # 'summary'
            return self._summary_hint(section)

    def _first_sentence_hint(self, section: CollapsedSection) -> str:
        """Generate hint from first sentence."""
        # Extract first sentence
        match = re.search(r'^(.+?[.!?])', section.content, re.MULTILINE)
        if match:
            first = match.group(1).strip()
            if len(first) < 80:
                return f"Expand: {first}"

        # Fallback to summary strategy
        return self._summary_hint(section)

    def _keywords_hint(self, section: CollapsedSection) -> str:
        """Generate hint from most common keywords."""
        # Get top 3 keywords
        keyword_list = list(section.keywords)
        if len(keyword_list) >= 3:
            top = keyword_list[:3]
            return f"Expand to see: {', '.join(top)}"

        # Fallback
        return self._summary_hint(section)

    def _summary_hint(self, section: CollapsedSection) -> str:
        """Generate hint by counting content elements."""
        content = section.content

        # Count elements
        code_blocks = len(re.findall(r'```', content)) // 2
        commands = len(re.findall(r'^\s*(?:python|bash|npm|docker|git)', content, re.MULTILINE))
        bullet_points = len(re.findall(r'^\s*[-*]\s', content, re.MULTILINE))
        tables = len(re.findall(r'^\|.*\|$', content, re.MULTILINE)) > 2

        # Generate hint based on content
        parts = []
        if code_blocks > 0:
            parts.append(f"{code_blocks} code example{'s' if code_blocks > 1 else ''}")
        if commands > 0:
            parts.append(f"{commands} command{'s' if commands > 1 else ''}")
        if bullet_points > 0:
            parts.append(f"{bullet_points} item{'s' if bullet_points > 1 else ''}")
        if tables:
            parts.append("reference tables")

        if parts:
            return "Expand to see: " + ", ".join(parts)
        else:
            # Generic hint
            char_count = len(content)
            return f"Expand for details ({char_count} chars)"

    def check_hints(self, sections: List[CollapsedSection]) -> List[Dict[str, Any]]:
        """
        Check if expand hints are helpful.

        Args:
            sections: List of CollapsedSection objects

        Returns:
            List of issue dicts
        """
        issues = []

        for section in sections:
            # Check if summary has a good expand hint
            if not any(phrase in section.summary.lower() for phrase in ['expand', 'see', 'show', 'view']):
                suggested_hint = self.generate_hint(section)

                # Confidence: high if hint is specific, lower if generic
                confidence = 0.85 if 'code example' in suggested_hint or 'command' in suggested_hint else 0.7

                issues.append({
                    'section': section,
                    'issue_type': 'poor_hint',
                    'description': f"Section '{section.title}' lacks expand hint",
                    'suggested_fix': f"Add hint: {suggested_hint}",
                    'confidence': confidence
                })

        return issues


class UnusedSectionDetector:
    """Detect sections that are never expanded (potentially unused)."""

    def __init__(self, long_section_threshold: int = 500, track_usage: bool = False):
        """
        Initialize detector.

        Args:
            long_section_threshold: Line count above which sections are flagged as suspicious
            track_usage: Whether to track usage (requires external analytics)
        """
        self.long_section_threshold = long_section_threshold
        self.track_usage = track_usage

    def detect_unused(self, sections: List[CollapsedSection]) -> List[Dict[str, Any]]:
        """
        Detect potentially unused sections.

        Heuristics:
        - Very long content (> threshold lines) that's always collapsed = probably never read
        - Content references deprecated features (TODO)
        - Content not referenced anywhere else (TODO)

        Args:
            sections: List of CollapsedSection objects

        Returns:
            List of issue dicts
        """
        issues = []

        for section in sections:
            content_lines = section.content.count('\n')

            # Very long sections are suspicious
            if content_lines > self.long_section_threshold:
                # Lower confidence - this is a weak signal
                confidence = 0.6 if content_lines > self.long_section_threshold * 2 else 0.5

                issues.append({
                    'section': section,
                    'issue_type': 'unused',
                    'description': f"Very long collapsed section ({content_lines} lines) - possibly never read",
                    'suggested_fix': "Consider archiving or moving to separate file",
                    'confidence': confidence
                })

            # TODO: Check if content references deprecated features
            # TODO: Check if content is referenced elsewhere

        return issues


class ManageCollapsedHealer(HealingSystem):
    """
    Universal healer for managing collapsed sections.

    Configuration keys (in config['healers']['manage_collapsed']):
        - hint_strategy: 'first_sentence', 'keywords', or 'summary'
        - track_usage: bool - whether to track usage analytics
        - long_section_threshold: int - line count for flagging long sections
        - missing_keywords_threshold: float - ratio for flagging missing keywords
        - stopwords: List[str] - words to exclude from keyword extraction
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize healer with configuration."""
        super().__init__(config)

        # Get healer-specific config
        healer_config = config.get('healers', {}).get('manage_collapsed', {})

        # Initialize components
        stopwords = set(healer_config.get('stopwords', []))
        self.extractor = CollapsedSectionExtractor(stopwords if stopwords else None)

        self.hint_generator = ExpandHintGenerator(
            strategy=healer_config.get('hint_strategy', 'summary')
        )

        self.unused_detector = UnusedSectionDetector(
            long_section_threshold=healer_config.get('long_section_threshold', 500),
            track_usage=healer_config.get('track_usage', False)
        )

        self.index_checker = SearchIndexChecker()

        # Config options
        self.missing_keywords_threshold = healer_config.get('missing_keywords_threshold', 0.5)

    def check(self) -> HealingReport:
        """
        Analyze collapsed sections and return issues found.

        Returns:
            HealingReport with mode="check"
        """
        start_time = time.time()
        changes = []

        # Find all markdown files in doc_root
        md_files = list(self.doc_root.rglob('*.md'))

        for md_file in md_files:
            sections = self.extractor.extract(md_file)

            if not sections:
                continue

            # Check expand hints
            hint_issues = self.hint_generator.check_hints(sections)

            # Detect unused sections
            unused_issues = self.unused_detector.detect_unused(sections)

            # Convert issues to Change objects
            for issue in hint_issues + unused_issues:
                section = issue['section']

                # Create change proposal
                old_summary = f"<summary>{section.summary}</summary>"

                if issue['issue_type'] == 'poor_hint':
                    # Extract hint from suggested_fix
                    hint_match = re.search(r'Add hint: (.+)', issue['suggested_fix'])
                    if hint_match:
                        hint = hint_match.group(1)
                        new_summary = f"<summary>{section.title} ({hint})</summary>"

                        changes.append(Change(
                            file=section.file,
                            line=section.start_line,
                            old_content=old_summary,
                            new_content=new_summary,
                            confidence=issue['confidence'],
                            reason=issue['description'],
                            healer='ManageCollapsedHealer'
                        ))

                elif issue['issue_type'] == 'unused':
                    # For unused sections, just flag (don't auto-fix)
                    # Low confidence - requires manual review
                    changes.append(Change(
                        file=section.file,
                        line=section.start_line,
                        old_content='',  # No automatic fix
                        new_content='',
                        confidence=issue['confidence'],
                        reason=issue['description'] + ' (manual review needed)',
                        healer='ManageCollapsedHealer'
                    ))

        execution_time = time.time() - start_time

        return self.create_report(
            mode='check',
            issues_found=len(changes),
            issues_fixed=0,
            changes=changes,
            execution_time=execution_time
        )

    def heal(self, min_confidence: Optional[float] = None) -> HealingReport:
        """
        Apply fixes to collapsed sections above confidence threshold.

        Args:
            min_confidence: Override default confidence threshold

        Returns:
            HealingReport with mode="heal"
        """
        start_time = time.time()

        # Get issues
        check_report = self.check()

        # Filter by confidence
        threshold = min_confidence if min_confidence is not None else self.min_confidence
        changes_to_apply = [c for c in check_report.changes if c.confidence >= threshold]

        # Apply changes
        applied = []
        for change in changes_to_apply:
            # Skip changes with no fix (e.g., unused sections needing manual review)
            if not change.old_content and not change.new_content:
                continue

            if self.validate_change(change):
                if self.apply_change(change):
                    applied.append(change)
                else:
                    self.log_error(f"Failed to apply change to {change.file}:{change.line}")
            else:
                self.log_error(f"Validation failed for {change.file}:{change.line}")

        execution_time = time.time() - start_time

        return self.create_report(
            mode='heal',
            issues_found=check_report.issues_found,
            issues_fixed=len(applied),
            changes=applied,
            execution_time=execution_time
        )

    def archive_unused(self, sections: List[CollapsedSection]) -> int:
        """
        Archive unused sections to separate file (with user approval).

        This method requires interactive approval and is NOT auto-applied.

        Args:
            sections: List of CollapsedSection objects to archive

        Returns:
            Number of sections archived
        """
        # TODO: Implement archiving workflow
        # 1. Create archive file if not exists
        # 2. Append sections to archive
        # 3. Remove from source files
        # 4. Return count

        return 0
