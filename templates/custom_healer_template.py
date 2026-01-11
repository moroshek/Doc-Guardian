"""
Custom Healer Template for Doc Guardian

Copy this file to create your own healer:
1. Copy to: doc-guardian/guardian/healers/my_custom_healer.py
2. Rename class to match your healer (e.g., FixTyposHealer)
3. Implement check() and heal() methods
4. Register in config.toml

Example configuration in config.toml:
    [healers.my_custom]
    enabled = true
    option1 = "value"
    option2 = 42

For complete guide: See docs/CUSTOM_HEALERS.md
"""

from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
import re

from guardian.core.base import HealingSystem, HealingReport, Change
from guardian.core.confidence import (
    calculate_confidence,
    ConfidenceFactors,
    assess_change_magnitude,
    assess_risk_level
)
from guardian.core.logger import setup_logger


class CustomHealerTemplate(HealingSystem):
    """
    Custom healer for [describe what it does].

    This healer addresses [specific documentation problem it solves].

    Use Cases:
        - [Use case 1]
        - [Use case 2]
        - [Use case 3]

    Configuration:
        [healers.custom_template]
        enabled = true
        option1 = "default_value"
        option2 = 42
        min_confidence = 0.85  # Optional override

    Example:
        >>> from guardian.core.config_loader import load_config
        >>> config = load_config("config.toml")
        >>> healer = CustomHealerTemplate(config)
        >>>
        >>> # Check for issues
        >>> report = healer.check()
        >>> print(f"Found {report.issues_found} issues")
        >>>
        >>> # Apply fixes above confidence threshold
        >>> if report.issues_found > 0:
        ...     heal_report = healer.heal(min_confidence=0.90)
        ...     print(f"Fixed {heal_report.issues_fixed}/{heal_report.issues_found}")
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize custom healer with configuration.

        Args:
            config: Configuration dict from config.toml

        Raises:
            KeyError: If required config keys are missing
        """
        super().__init__(config)

        # Load healer-specific config with defaults
        custom_config = config.get('healers', {}).get('custom_template', {})

        # Required options (raise if missing)
        # if 'required_option' not in custom_config:
        #     raise KeyError("Missing required config: healers.custom_template.required_option")

        # Optional options with defaults
        self.option1 = custom_config.get('option1', 'default_value')
        self.option2 = custom_config.get('option2', 42)

        # Override min_confidence if specified
        if 'min_confidence' in custom_config:
            self.min_confidence = custom_config['min_confidence']

        # Setup logging
        self.logger = setup_logger('custom_template')

        # Compile regex patterns if needed
        # self.pattern = re.compile(r'your_regex_pattern')

        # Statistics for reporting
        self.stats = {
            'files_scanned': 0,
            'issues_detected': 0,
            'fixes_applied': 0
        }

    def check(self) -> HealingReport:
        """
        Analyze documentation and identify issues.

        Workflow:
            1. Find all relevant files
            2. Analyze each file for issues
            3. Propose fixes with confidence scores
            4. Return report with proposed changes

        Returns:
            HealingReport with mode="check" and list of proposed changes

        Example:
            >>> report = healer.check()
            >>> if report.issues_found > 0:
            ...     for change in report.changes:
            ...         print(f"Issue in {change.file}:{change.line}")
            ...         print(f"  Confidence: {change.confidence:.2%}")
            ...         print(f"  Reason: {change.reason}")
        """
        issues: List[Change] = []
        errors: List[str] = []
        start_time = datetime.now()

        self.logger.info("Starting check...")

        try:
            # Step 1: Find all markdown files (or whatever files you need)
            files = self._find_target_files()
            self.stats['files_scanned'] = len(files)

            self.logger.info(f"Scanning {len(files)} files...")

            # Step 2: Analyze each file
            for file_path in files:
                try:
                    file_issues = self._analyze_file(file_path)
                    issues.extend(file_issues)
                    self.stats['issues_detected'] += len(file_issues)

                except Exception as e:
                    error_msg = f"Failed to analyze {file_path}: {e}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)

        except Exception as e:
            error_msg = f"Check operation failed: {e}"
            self.logger.error(error_msg)
            errors.append(error_msg)

        execution_time = (datetime.now() - start_time).total_seconds()

        self.logger.info(f"Check complete: {len(issues)} issues found in {execution_time:.2f}s")

        return HealingReport(
            healer_name="custom_template",
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
        Apply fixes above confidence threshold.

        Workflow:
            1. Run check() to identify issues
            2. Filter changes by confidence threshold
            3. Validate each change
            4. Apply validated changes
            5. Return report with results

        Args:
            min_confidence: Override default confidence threshold (0.0-1.0)

        Returns:
            HealingReport with mode="heal" and list of applied changes

        Example:
            >>> # Apply only high-confidence fixes
            >>> report = healer.heal(min_confidence=0.95)
            >>> print(f"Fixed {report.issues_fixed} issues")
            >>>
            >>> # Check if any errors occurred
            >>> if report.has_errors:
            ...     print("Errors:", report.errors)
        """
        start_time = datetime.now()

        # Get issues from check
        self.logger.info("Running check to identify issues...")
        check_report = self.check()

        threshold = min_confidence or self.min_confidence
        self.logger.info(f"Applying fixes with confidence >= {threshold:.2%}")

        # Filter by confidence threshold
        eligible_changes = [
            change for change in check_report.changes
            if change.confidence >= threshold
        ]

        self.logger.info(f"{len(eligible_changes)}/{len(check_report.changes)} changes above threshold")

        # Apply fixes
        applied: List[Change] = []
        errors: List[str] = []

        for change in eligible_changes:
            try:
                # Validate before applying
                if not self.validate_change(change):
                    error_msg = f"Validation failed for {change.file}:{change.line}"
                    self.logger.warning(error_msg)
                    errors.append(error_msg)
                    continue

                # Apply the change
                if self.apply_change(change):
                    applied.append(change)
                    self.stats['fixes_applied'] += 1
                    self.logger.info(f"✓ Applied: {change.reason}")
                else:
                    error_msg = f"Failed to apply change to {change.file}:{change.line}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)

            except Exception as e:
                error_msg = f"Error applying change to {change.file}: {e}"
                self.logger.error(error_msg)
                errors.append(error_msg)

        execution_time = (datetime.now() - start_time).total_seconds()

        self.logger.info(f"Heal complete: {len(applied)}/{len(check_report.changes)} fixes applied in {execution_time:.2f}s")

        return HealingReport(
            healer_name="custom_template",
            mode="heal",
            timestamp=datetime.now().isoformat(),
            issues_found=len(check_report.changes),
            issues_fixed=len(applied),
            changes=applied,
            errors=check_report.errors + errors,
            execution_time=execution_time
        )

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _find_target_files(self) -> List[Path]:
        """
        Find all files to analyze.

        Override this to customize which files to process.

        Returns:
            List of Path objects to analyze
        """
        # Example: Find all markdown files
        return list(self.doc_root.rglob("*.md"))

        # Example: Exclude certain directories
        # excluded = {'node_modules', '.git', '__pycache__'}
        # files = []
        # for md_file in self.doc_root.rglob("*.md"):
        #     if not any(excluded_dir in md_file.parts for excluded_dir in excluded):
        #         files.append(md_file)
        # return files

    def _analyze_file(self, file_path: Path) -> List[Change]:
        """
        Analyze a single file and return proposed changes.

        This is where your healer's main logic goes.

        Args:
            file_path: Path to file to analyze

        Returns:
            List of Change objects for issues found in this file
        """
        changes = []

        # Read file content
        try:
            content = file_path.read_text()
        except Exception as e:
            self.logger.error(f"Cannot read {file_path}: {e}")
            return []

        # Example: Look for specific pattern
        # for match in self.pattern.finditer(content):
        #     # Found an issue - create a fix
        #     change = self._create_fix(file_path, match, content)
        #     if change:
        #         changes.append(change)

        # Example: Line-by-line analysis
        lines = content.split('\n')
        for line_num, line in enumerate(lines, start=1):
            if self._has_issue(line):
                change = self._create_fix_for_line(
                    file_path=file_path,
                    line_num=line_num,
                    line_content=line,
                    full_content=content
                )
                if change:
                    changes.append(change)

        return changes

    def _has_issue(self, line: str) -> bool:
        """
        Check if a line has the issue this healer addresses.

        Override this with your detection logic.

        Args:
            line: Line of text to check

        Returns:
            True if issue detected, False otherwise
        """
        # Example: Detect lines with TODO comments
        # return 'TODO:' in line and not line.strip().startswith('#')

        return False  # Replace with your logic

    def _create_fix_for_line(
        self,
        file_path: Path,
        line_num: int,
        line_content: str,
        full_content: str
    ) -> Optional[Change]:
        """
        Create a Change object for fixing an issue on a specific line.

        Override this with your fix generation logic.

        Args:
            file_path: Path to file containing issue
            line_num: Line number (1-indexed)
            line_content: Content of the line with issue
            full_content: Full file content (for context)

        Returns:
            Change object, or None if no fix could be generated
        """
        # Example: Generate fix
        # old_content = line_content
        # new_content = self._generate_fix(line_content)

        # Calculate confidence
        # confidence = self._calculate_confidence(old_content, new_content, file_path)

        # return Change(
        #     file=file_path,
        #     line=line_num,
        #     old_content=old_content,
        #     new_content=new_content,
        #     confidence=confidence,
        #     reason=f"[Clear explanation of why this change is needed]",
        #     healer="custom_template"
        # )

        return None  # Replace with your logic

    def _calculate_confidence(
        self,
        old_content: str,
        new_content: str,
        file_path: Path
    ) -> float:
        """
        Calculate confidence score for a proposed fix.

        Uses multi-factor confidence model. Override to customize scoring.

        Args:
            old_content: Original content
            new_content: Proposed new content
            file_path: File being modified (for context)

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Use multi-factor confidence model
        factors = ConfidenceFactors(
            pattern_match=0.95,      # How well did we match the pattern? (0.0-1.0)
            change_magnitude=assess_change_magnitude(old_content, new_content),  # Size of change
            risk_assessment=assess_risk_level('typo_fix'),  # Risk level of this change type
            historical_accuracy=0.92  # Historical success rate for this type of fix
        )

        return calculate_confidence(factors)

    def validate_change(self, change: Change) -> bool:
        """
        Validate a change before applying.

        Override to add custom validation logic.
        Default validation from HealingSystem base class:
        - File exists
        - Old content matches current file
        - New content is non-empty

        Args:
            change: Change object to validate

        Returns:
            True if change is valid and safe to apply
        """
        # Call base class validation first
        if not super().validate_change(change):
            return False

        # Add custom validation here
        # Example: Check file is not read-only
        # if not os.access(change.file, os.W_OK):
        #     self.logger.error(f"File is read-only: {change.file}")
        #     return False

        # Example: Validate new content is syntactically correct
        # if not self._is_valid_markdown(change.new_content):
        #     self.logger.error(f"Generated invalid markdown")
        #     return False

        return True


# ============================================================================
# Example Usage & Testing
# ============================================================================

if __name__ == "__main__":
    """
    Example usage of custom healer.

    Run this script directly to test your healer:
        python custom_healer_template.py
    """

    # Configuration
    config = {
        'project': {
            'root': '/path/to/your/project',
            'doc_root': '/path/to/your/project/docs'
        },
        'healers': {
            'custom_template': {
                'enabled': True,
                'option1': 'test_value',
                'option2': 100
            }
        },
        'confidence': {
            'auto_commit_threshold': 0.90,
            'auto_stage_threshold': 0.80
        }
    }

    # Create healer
    print("Initializing healer...")
    healer = CustomHealerTemplate(config)

    # Run check
    print("\nRunning check...")
    check_report = healer.check()

    print(f"\nCheck Results:")
    print(f"  Files scanned: {healer.stats['files_scanned']}")
    print(f"  Issues found: {check_report.issues_found}")
    print(f"  Execution time: {check_report.execution_time:.2f}s")

    if check_report.has_errors:
        print(f"\nErrors encountered:")
        for error in check_report.errors:
            print(f"  - {error}")

    # Show sample issues
    if check_report.changes:
        print(f"\nSample issues (showing first 5):")
        for change in check_report.changes[:5]:
            print(f"\n  {change.file}:{change.line}")
            print(f"    Confidence: {change.confidence:.2%}")
            print(f"    Reason: {change.reason}")
            print(f"    Old: {change.old_content[:50]}...")
            print(f"    New: {change.new_content[:50]}...")

    # Run heal if issues found
    if check_report.issues_found > 0:
        print(f"\nRunning heal (threshold: {config['confidence']['auto_commit_threshold']:.2%})...")
        heal_report = healer.heal()

        print(f"\nHeal Results:")
        print(f"  Issues fixed: {heal_report.issues_fixed}/{heal_report.issues_found}")
        print(f"  Success rate: {heal_report.success_rate:.2%}")
        print(f"  Execution time: {heal_report.execution_time:.2f}s")

        if heal_report.has_errors:
            print(f"\nErrors during healing:")
            for error in heal_report.errors:
                print(f"  - {error}")
    else:
        print("\nNo issues found - documentation is healthy!")
