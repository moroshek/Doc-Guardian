"""
Fix Common Typos Healer

Complete working example of a custom healer for Doc Guardian.

Features:
- Dictionary-based typo detection
- Case-preserving replacements
- Skip code blocks and inline code
- High-confidence auto-commit
- Configurable typo dictionary

Author: Doc Guardian Examples
License: MIT
"""

from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
import re
from collections import Counter

from guardian.core.base import HealingSystem, HealingReport, Change
from guardian.core.confidence import (
    calculate_confidence,
    ConfidenceFactors,
    assess_change_magnitude,
    assess_risk_level
)
from guardian.core.logger import setup_logger


class FixTyposHealer(HealingSystem):
    """
    Auto-fix common typos in documentation.

    This healer uses a configurable dictionary to detect and fix
    common typos with high confidence (typically 0.95+).

    Configuration:
        [healers.fix_typos]
        enabled = true
        min_confidence = 0.90
        case_sensitive = false
        preserve_case = true
        skip_code_blocks = true

        [healers.fix_typos.common_typos]
        teh = "the"
        recieve = "receive"

    Example:
        >>> config = load_config("config.toml")
        >>> healer = FixTyposHealer(config)
        >>> report = healer.check()
        >>> print(f"Found {report.issues_found} typos")
        >>> heal_report = healer.heal()
        >>> print(f"Fixed {heal_report.issues_fixed} typos")
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize typo healer with configuration."""
        super().__init__(config)

        # Load healer config
        typo_config = config.get('healers', {}).get('fix_typos', {})

        # Load typo dictionary
        self.typo_map = typo_config.get('common_typos', {
            'teh': 'the',
            'recieve': 'receive',
            'occured': 'occurred',
            'seperator': 'separator',
            'wierd': 'weird',
            'thier': 'their',
            'definately': 'definitely',
            'untill': 'until'
        })

        # Options
        self.case_sensitive = typo_config.get('case_sensitive', False)
        self.preserve_case = typo_config.get('preserve_case', True)
        self.skip_code_blocks = typo_config.get('skip_code_blocks', True)

        # Setup logging
        self.logger = setup_logger('fix_typos')

        # Pre-compile regex patterns for performance
        self._compile_patterns()

        # Statistics
        self.stats = {
            'files_scanned': 0,
            'typos_found': 0,
            'typos_by_type': Counter(),
            'files_with_typos': set()
        }

        self.logger.info(f"Loaded {len(self.typo_map)} typos in dictionary")

    def _compile_patterns(self):
        """Pre-compile regex patterns for each typo."""
        self.typo_patterns = {}

        for typo, correction in self.typo_map.items():
            # Word boundary pattern
            flags = 0 if self.case_sensitive else re.IGNORECASE
            pattern = rf'\b{re.escape(typo)}\b'
            self.typo_patterns[typo] = re.compile(pattern, flags)

    def check(self) -> HealingReport:
        """
        Scan documentation for typos.

        Returns:
            HealingReport with proposed typo fixes
        """
        issues: List[Change] = []
        errors: List[str] = []
        start_time = datetime.now()

        self.logger.info("Scanning for typos...")

        try:
            # Find all markdown files
            files = self._find_markdown_files()
            self.stats['files_scanned'] = len(files)

            self.logger.info(f"Scanning {len(files)} files...")

            # Analyze each file
            for file_path in files:
                try:
                    file_issues = self._analyze_file(file_path)
                    if file_issues:
                        issues.extend(file_issues)
                        self.stats['files_with_typos'].add(file_path)

                except Exception as e:
                    error_msg = f"Failed to analyze {file_path}: {e}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)

            # Update stats
            self.stats['typos_found'] = len(issues)

        except Exception as e:
            error_msg = f"Check operation failed: {e}"
            self.logger.error(error_msg)
            errors.append(error_msg)

        execution_time = (datetime.now() - start_time).total_seconds()

        self.logger.info(
            f"Check complete: {len(issues)} typos in "
            f"{len(self.stats['files_with_typos'])}/{self.stats['files_scanned']} files "
            f"({execution_time:.2f}s)"
        )

        return HealingReport(
            healer_name="fix_typos",
            mode="check",
            timestamp=datetime.now().isoformat(),
            issues_found=len(issues),
            issues_fixed=0,
            changes=issues,
            errors=errors,
            execution_time=execution_time
        )

    def heal(self, min_confidence: Optional[float] = None) -> HealingReport:
        """
        Apply typo fixes above confidence threshold.

        Args:
            min_confidence: Override default threshold (default: 0.90)

        Returns:
            HealingReport with applied fixes
        """
        start_time = datetime.now()

        # Get issues
        check_report = self.check()
        threshold = min_confidence or self.min_confidence

        self.logger.info(f"Applying fixes with confidence >= {threshold:.2%}")

        # Filter by confidence
        eligible = [c for c in check_report.changes if c.confidence >= threshold]
        self.logger.info(f"{len(eligible)}/{len(check_report.changes)} above threshold")

        # Apply fixes
        applied: List[Change] = []
        errors: List[str] = []

        for change in eligible:
            try:
                if self.validate_change(change) and self.apply_change(change):
                    applied.append(change)
                    self.logger.info(f"✓ {change.reason}")
                else:
                    errors.append(f"Failed to apply: {change.reason}")

            except Exception as e:
                error_msg = f"Error applying {change.reason}: {e}"
                self.logger.error(error_msg)
                errors.append(error_msg)

        execution_time = (datetime.now() - start_time).total_seconds()

        self.logger.info(
            f"Heal complete: {len(applied)}/{len(check_report.changes)} fixed "
            f"({execution_time:.2f}s)"
        )

        return HealingReport(
            healer_name="fix_typos",
            mode="heal",
            timestamp=datetime.now().isoformat(),
            issues_found=len(check_report.changes),
            issues_fixed=len(applied),
            changes=applied,
            errors=check_report.errors + errors,
            execution_time=execution_time
        )

    def _find_markdown_files(self) -> List[Path]:
        """Find all markdown files in doc_root."""
        return list(self.doc_root.rglob("*.md"))

    def _analyze_file(self, file_path: Path) -> List[Change]:
        """
        Analyze file for typos.

        Args:
            file_path: Path to markdown file

        Returns:
            List of Change objects for typos found
        """
        changes = []

        # Read content
        try:
            content = file_path.read_text()
        except Exception as e:
            self.logger.error(f"Cannot read {file_path}: {e}")
            return []

        # Split into lines
        lines = content.split('\n')
        in_code_block = False

        for line_num, line in enumerate(lines, start=1):
            # Track code blocks
            if self.skip_code_blocks and line.strip().startswith('```'):
                in_code_block = not in_code_block
                continue

            # Skip code blocks
            if in_code_block:
                continue

            # Skip inline code (simple heuristic)
            if '`' in line:
                # Skip lines with inline code
                continue

            # Check for typos
            typos_in_line = self._find_typos_in_line(line)

            if typos_in_line:
                # Create fix for this line
                change = self._create_fix(
                    file_path=file_path,
                    line_num=line_num,
                    line=line,
                    typos=typos_in_line
                )
                if change:
                    changes.append(change)

                    # Update stats
                    for typo, _ in typos_in_line:
                        self.stats['typos_by_type'][typo] += 1

        return changes

    def _find_typos_in_line(self, line: str) -> List[tuple]:
        """
        Find all typos in a line.

        Args:
            line: Line of text to check

        Returns:
            List of (typo, correction) tuples
        """
        found = []

        for typo, correction in self.typo_map.items():
            pattern = self.typo_patterns[typo]
            if pattern.search(line):
                found.append((typo, correction))

        return found

    def _create_fix(
        self,
        file_path: Path,
        line_num: int,
        line: str,
        typos: List[tuple]
    ) -> Optional[Change]:
        """
        Create Change object for fixing typos in line.

        Args:
            file_path: Path to file
            line_num: Line number
            line: Original line content
            typos: List of (typo, correction) tuples

        Returns:
            Change object or None
        """
        # Apply all fixes to line
        fixed_line = line
        for typo, correction in typos:
            pattern = self.typo_patterns[typo]

            if self.preserve_case:
                # Case-preserving replacement
                fixed_line = self._replace_preserve_case(
                    fixed_line, pattern, typo, correction
                )
            else:
                # Direct replacement
                fixed_line = pattern.sub(correction, fixed_line)

        # Calculate confidence
        confidence = self._calculate_confidence(line, fixed_line, typos)

        # Create change
        typo_list = ', '.join(t[0] for t in typos)
        return Change(
            file=file_path,
            line=line_num,
            old_content=line,
            new_content=fixed_line,
            confidence=confidence,
            reason=f"Fix typo(s): {typo_list}",
            healer="fix_typos"
        )

    def _replace_preserve_case(
        self,
        text: str,
        pattern: re.Pattern,
        typo: str,
        correction: str
    ) -> str:
        """
        Replace typo with correction, preserving original case.

        Examples:
            teh → the
            Teh → The
            TEH → THE
        """
        def replace_func(match):
            original = match.group(0)

            # All uppercase
            if original.isupper():
                return correction.upper()
            # Title case
            elif original[0].isupper():
                return correction.capitalize()
            # Lowercase
            else:
                return correction.lower()

        return pattern.sub(replace_func, text)

    def _calculate_confidence(
        self,
        old_line: str,
        new_line: str,
        typos: List[tuple]
    ) -> float:
        """
        Calculate confidence for typo fix.

        Typo fixes are very high confidence because:
        - Exact dictionary match (pattern_match = 1.0)
        - Usually small changes (change_magnitude ≈ 0.95)
        - Very low risk (risk_assessment = 1.0)
        - High historical accuracy (0.95+)

        Args:
            old_line: Original line
            new_line: Fixed line
            typos: List of typos fixed

        Returns:
            Confidence score (typically 0.95-0.98)
        """
        factors = ConfidenceFactors(
            pattern_match=1.0,  # Exact dictionary match
            change_magnitude=assess_change_magnitude(old_line, new_line),
            risk_assessment=assess_risk_level('typo_fix'),  # = 1.0
            historical_accuracy=0.95  # Typo fixes rarely wrong
        )

        return calculate_confidence(factors)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about typos found.

        Returns:
            Dictionary with stats
        """
        most_common = self.stats['typos_by_type'].most_common(5)

        return {
            'files_scanned': self.stats['files_scanned'],
            'files_with_typos': len(self.stats['files_with_typos']),
            'total_typos': self.stats['typos_found'],
            'most_common_typos': most_common,
            'unique_typos': len(self.stats['typos_by_type'])
        }


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    """Test the healer with sample configuration."""

    config = {
        'project': {
            'root': '/tmp/test_project',
            'doc_root': '/tmp/test_project/docs'
        },
        'healers': {
            'fix_typos': {
                'enabled': True,
                'min_confidence': 0.90,
                'common_typos': {
                    'teh': 'the',
                    'recieve': 'receive',
                    'occured': 'occurred'
                }
            }
        },
        'confidence': {
            'auto_commit_threshold': 0.90
        }
    }

    # Create test directory and sample file
    from pathlib import Path
    test_dir = Path('/tmp/test_project/docs')
    test_dir.mkdir(parents=True, exist_ok=True)

    sample_file = test_dir / 'sample.md'
    sample_file.write_text("""# Sample Documentation

This file has some typos for testing.

Teh quick brown fox jumps over teh lazy dog.

We recieve emails when an error occured.

This is correct and has no typos.
""")

    # Create healer
    print("Initializing healer...")
    healer = FixTyposHealer(config)

    # Run check
    print("\nRunning check...")
    check_report = healer.check()

    print(f"\nCheck Results:")
    print(f"  Files scanned: {healer.stats['files_scanned']}")
    print(f"  Typos found: {check_report.issues_found}")

    if check_report.changes:
        print("\nTypos detected:")
        for change in check_report.changes:
            print(f"  Line {change.line}: {change.reason}")
            print(f"    Old: {change.old_content.strip()}")
            print(f"    New: {change.new_content.strip()}")
            print(f"    Confidence: {change.confidence:.2%}")

    # Run heal
    if check_report.issues_found > 0:
        print("\nRunning heal...")
        heal_report = healer.heal()

        print(f"\nHeal Results:")
        print(f"  Fixed: {heal_report.issues_fixed}/{heal_report.issues_found}")
        print(f"  Success rate: {heal_report.success_rate:.2%}")

        # Show fixed content
        print("\nFixed content:")
        print(sample_file.read_text())

        # Show stats
        stats = healer.get_stats()
        print("\nStatistics:")
        print(f"  Files with typos: {stats['files_with_typos']}")
        print(f"  Most common typos:")
        for typo, count in stats['most_common_typos']:
            print(f"    {typo}: {count}")
