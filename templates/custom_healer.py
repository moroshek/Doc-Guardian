"""
Custom Healer Template for Doc Guardian.

This template provides a starting point for creating custom documentation healers.
Follow the instructions in the comments to implement your own healer.

Usage:
    1. Copy this file to guardian/healers/your_healer.py
    2. Rename the class
    3. Implement check() and heal() methods
    4. Register in guardian/healers/__init__.py
    5. Add configuration section to config.toml

Example configuration:
    [healers.your_healer]
    enabled = true
    your_custom_option = "value"
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import time

# Import base classes
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from guardian.core.base import HealingSystem, HealingReport, Change
from guardian.core.confidence import calculate_confidence, ConfidenceFactors


class CustomHealer(HealingSystem):
    """
    Custom documentation healer template.

    Rename this class to match your healer's purpose.
    Example: SpellingCheckerHealer, TocValidatorHealer, etc.

    Attributes:
        config: Configuration dictionary from config.toml/yaml
        project_root: Path to project root directory
        doc_root: Path to documentation root directory
        errors: List of errors encountered during healing
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the healer with configuration.

        Args:
            config: Full configuration dictionary. Access your healer's
                    config via config.get('healers', {}).get('your_healer', {})

        Raises:
            KeyError: If required project.root or project.doc_root is missing
        """
        # Call parent constructor - this sets up project_root, doc_root, errors
        super().__init__(config)

        # Get healer-specific configuration
        healer_config = config.get('healers', {}).get('custom_healer', {})

        # Example: Load a custom threshold option
        self.custom_threshold = healer_config.get('custom_threshold', 0.8)

        # Example: Load a list option
        self.patterns = healer_config.get('patterns', [])

        # Example: Build any indices or caches needed for scanning
        self._file_index: Dict[str, Path] = {}

    def _build_file_index(self) -> None:
        """
        Build an index of files for O(1) lookup.

        Call this at the start of check() if you need fast file lookups.
        """
        for file_path in self.doc_root.rglob("*.md"):
            self._file_index[file_path.stem.lower()] = file_path
            self._file_index[file_path.name.lower()] = file_path

    def _scan_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Scan a single file for issues.

        Override this method with your scanning logic.

        Args:
            file_path: Path to file to scan

        Returns:
            List of issue dictionaries, each containing:
                - line: Line number where issue occurs
                - old_content: Content to be replaced
                - new_content: Proposed fix
                - confidence: Confidence score (0.0-1.0)
                - reason: Human-readable explanation
        """
        issues = []

        try:
            content = file_path.read_text()
            lines = content.split('\n')

            for i, line in enumerate(lines, 1):
                # Example: Check for TODO comments
                if 'TODO' in line and 'DONE' not in line:
                    issues.append({
                        'line': i,
                        'old_content': line,
                        'new_content': line + ' <!-- Needs attention -->',
                        'confidence': 0.7,
                        'reason': 'Found TODO comment without resolution'
                    })

        except Exception as e:
            self.log_error(f"Error scanning {file_path}: {e}")

        return issues

    def _calculate_issue_confidence(self, issue: Dict[str, Any]) -> float:
        """
        Calculate confidence score for an issue.

        Override this to customize confidence calculation.

        Args:
            issue: Issue dictionary from _scan_file()

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Use the 4-factor confidence model
        factors = ConfidenceFactors(
            pattern_quality=0.9,      # How well the pattern matched
            change_magnitude=0.8,     # Smaller changes = higher confidence
            risk_level=0.9,           # Content changes are lower risk
            historical_success=0.85   # Past success rate
        )

        return calculate_confidence(factors)

    def check(self) -> HealingReport:
        """
        Check for issues without making changes.

        This method should:
        1. Scan all relevant files
        2. Identify issues
        3. Create Change objects for each issue
        4. Return a report with mode="check"

        Returns:
            HealingReport with list of proposed changes
        """
        start_time = time.time()
        changes = []
        self.errors = []  # Reset errors

        # Build file index for fast lookups
        self._build_file_index()

        # Scan all markdown files
        for file_path in self.doc_root.rglob("*.md"):
            # Skip excluded directories
            if any(part.startswith('.') for part in file_path.parts):
                continue

            issues = self._scan_file(file_path)

            for issue in issues:
                confidence = self._calculate_issue_confidence(issue)

                changes.append(Change(
                    file=file_path,
                    line=issue['line'],
                    old_content=issue['old_content'],
                    new_content=issue['new_content'],
                    confidence=confidence,
                    reason=issue['reason'],
                    healer=self.__class__.__name__
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
        Apply fixes above confidence threshold.

        This method should:
        1. Call check() to get proposed changes
        2. Filter by confidence threshold
        3. Validate each change
        4. Apply validated changes
        5. Return a report with mode="heal"

        Args:
            min_confidence: Minimum confidence for auto-healing.
                           Defaults to config threshold or 0.9.

        Returns:
            HealingReport with list of applied changes
        """
        start_time = time.time()
        self.errors = []

        # Get threshold
        confidence_threshold = min_confidence or self.min_confidence

        # Get proposed changes
        check_report = self.check()

        # Filter by confidence
        high_confidence_changes = [
            c for c in check_report.changes
            if c.confidence >= confidence_threshold
        ]

        # Apply changes
        applied_changes = []
        for change in high_confidence_changes:
            # Validate before applying
            if self.validate_change(change):
                if self.apply_change(change):
                    applied_changes.append(change)
            else:
                self.log_error(f"Change validation failed for {change.file}")

        execution_time = time.time() - start_time

        return self.create_report(
            mode="heal",
            issues_found=len(check_report.changes),
            issues_fixed=len(applied_changes),
            changes=applied_changes,
            execution_time=execution_time
        )


# Example usage (for testing)
if __name__ == "__main__":
    import tempfile

    # Create a test configuration
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        docs_dir = temp_path / "docs"
        docs_dir.mkdir()

        # Create a test file
        test_file = docs_dir / "test.md"
        test_file.write_text("""# Test Document

TODO: Add more content here

This is a test document.
""")

        config = {
            "project": {
                "root": str(temp_path),
                "doc_root": str(docs_dir),
            },
            "healers": {
                "custom_healer": {
                    "enabled": True,
                    "custom_threshold": 0.8,
                }
            }
        }

        # Test the healer
        healer = CustomHealer(config)

        print("Running check mode...")
        check_report = healer.check()
        print(f"  Issues found: {check_report.issues_found}")
        print(f"  Execution time: {check_report.execution_time:.2f}s")

        for change in check_report.changes:
            print(f"  - {change.file.name}:{change.line} ({change.confidence:.0%})")
            print(f"    Reason: {change.reason}")

        print("\nRunning heal mode...")
        heal_report = healer.heal()
        print(f"  Issues found: {heal_report.issues_found}")
        print(f"  Issues fixed: {heal_report.issues_fixed}")
        print(f"  Success rate: {heal_report.success_rate:.0%}")
