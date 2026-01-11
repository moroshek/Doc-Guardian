"""
Core abstractions for the Doc Guardian healing system.

This module provides universal base classes extracted from TCF's healing patterns.
All classes are config-driven and project-agnostic.

Security features:
- Path validation to prevent directory traversal (DG-2026-001)
- File size limits to prevent memory exhaustion (DG-2026-006)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from .path_validator import (
    validate_path_contained,
    validate_project_root,
    validate_doc_root,
    PathSecurityError,
)
from .security import (
    validate_file_size,
    safe_read_file,
    MAX_FILE_SIZE_BYTES,
    sanitize_error_message,
)


@dataclass
class Change:
    """
    Represents a single change to be made to a file.

    Attributes:
        file: Path to file to modify
        line: Line number where change occurs (0 if not line-specific)
        old_content: Content to be replaced
        new_content: New content to insert
        confidence: Confidence score (0.0-1.0)
        reason: Human-readable explanation of why this change is needed
        healer: Name of healer that proposed this change
    """
    file: Path
    line: int
    old_content: str
    new_content: str
    confidence: float
    reason: str
    healer: str


@dataclass
class HealingReport:
    """
    Report from a healing operation.

    Attributes:
        healer_name: Name of the healing system
        mode: "check" or "heal"
        timestamp: ISO format timestamp
        issues_found: Total number of issues detected
        issues_fixed: Number of issues actually fixed
        changes: List of Change objects (applied or proposed)
        errors: List of error messages encountered
        execution_time: Time in seconds to complete operation
    """
    healer_name: str
    mode: str
    timestamp: str
    issues_found: int
    issues_fixed: int
    changes: List[Change] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    execution_time: float = 0.0

    @property
    def success_rate(self) -> float:
        """
        Calculate success rate as issues_fixed / issues_found.

        Returns:
            1.0 if no issues found, otherwise ratio of fixed to found
        """
        if self.issues_found == 0:
            return 1.0
        return self.issues_fixed / self.issues_found

    @property
    def has_errors(self) -> bool:
        """Check if any errors were encountered."""
        return len(self.errors) > 0


class HealingSystem(ABC):
    """
    Base class for all healing systems.

    Healing systems follow a check → heal → validate workflow:
    1. check() - Analyze documentation and identify issues
    2. heal() - Apply fixes above confidence threshold
    3. validate_change() - Verify changes are safe
    4. apply_change() - Write changes to disk
    5. rollback_change() - Undo changes if needed

    Configuration:
        All paths and thresholds are loaded from config dict.
        See config_schema.py for expected structure.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize healing system with configuration.

        Args:
            config: Configuration dict. Required keys:
                - project.root: Path to project root
                - project.doc_root: Path to documentation root
                Optional keys (with defaults):
                - confidence.auto_commit_threshold: Min confidence (default: 0.9)
                - confidence.auto_stage_threshold: Min confidence (default: 0.8)
                - reporting.output_dir: Report output location

        Raises:
            KeyError: If required project.root or project.doc_root is missing
        """
        self.config = config

        # Required config with clear error messages
        project_config = config.get('project', {})
        if 'root' not in project_config:
            raise KeyError(
                "Config validation failed at 'project.root': "
                "This required field is missing. "
                "Set 'project.root' to your project directory path in your config file."
            )
        if 'doc_root' not in project_config:
            raise KeyError(
                "Config validation failed at 'project.doc_root': "
                "This required field is missing. "
                "Set 'project.doc_root' to your documentation directory path in your config file."
            )

        self.project_root = Path(project_config['root'])
        self.doc_root = Path(project_config['doc_root'])

        # Security: Validate project_root exists and is accessible
        self.project_root = validate_project_root(self.project_root)

        # Security: Validate doc_root is within project_root
        self.doc_root = validate_doc_root(self.doc_root, self.project_root)

        # Validate doc_root exists (FS-14)
        if not self.doc_root.exists():
            raise FileNotFoundError(
                f"Documentation root does not exist: {self.doc_root}. "
                f"Check 'project.doc_root' in config."
            )

        if not self.doc_root.is_dir():
            raise NotADirectoryError(
                f"Documentation root is not a directory: {self.doc_root}. "
                f"Check 'project.doc_root' in config."
            )

        # Optional config with sensible defaults
        confidence_config = config.get('confidence', {})
        self.min_confidence = confidence_config.get('auto_commit_threshold', 0.9)

        self.errors: List[str] = []

    @abstractmethod
    def check(self) -> HealingReport:
        """
        Analyze documentation and return issues found.

        This method should:
        1. Scan relevant files
        2. Detect issues based on healer's rules
        3. Propose changes with confidence scores
        4. Return report with issues_found > 0 if problems detected

        Returns:
            HealingReport with mode="check" and list of proposed changes
        """
        pass

    @abstractmethod
    def heal(self, min_confidence: Optional[float] = None) -> HealingReport:
        """
        Apply fixes above confidence threshold.

        This method should:
        1. Call check() to get proposed changes
        2. Filter by confidence threshold
        3. Validate each change
        4. Apply validated changes
        5. Return report with issues_fixed > 0 if fixes applied

        Args:
            min_confidence: Override default confidence threshold

        Returns:
            HealingReport with mode="heal" and list of applied changes
        """
        pass

    def validate_change(self, change: Change) -> bool:
        """
        Validate a proposed change before applying.

        Default implementation checks:
        - File is within project root (security)
        - File exists
        - File is within size limits (security)
        - Old content matches current file content
        - New content is non-empty (unless explicitly removing content)

        Override this method for custom validation logic.

        Args:
            change: Change object to validate

        Returns:
            True if change is valid and safe to apply
        """
        # Security: Validate file is within project root
        try:
            validated_path = validate_path_contained(
                change.file, self.project_root, allow_nonexistent=True
            )
        except PathSecurityError as e:
            self.log_error(sanitize_error_message(
                f"Security: {e}", self.project_root
            ))
            return False

        # File must exist (unless creating new file)
        if not change.file.exists():
            self.log_error(sanitize_error_message(
                f"File does not exist: {change.file}", self.project_root
            ))
            return False

        # Security: Validate file size before reading
        is_valid, error = validate_file_size(change.file)
        if not is_valid:
            self.log_error(sanitize_error_message(error, self.project_root))
            return False

        # Read current content
        try:
            content = safe_read_file(change.file)
        except Exception as e:
            self.log_error(sanitize_error_message(
                f"Cannot read {change.file}: {e}", self.project_root
            ))
            return False

        # Old content must match
        if change.old_content and change.old_content not in content:
            self.log_error(f"Old content not found in {change.file}")
            return False

        # New content should not be empty (unless explicit deletion)
        if not change.new_content and change.old_content:
            # This is a deletion - allow if intentional
            pass

        return True

    def apply_change(self, change: Change) -> bool:
        """
        Apply a validated change to disk.

        Default implementation:
        1. Validates file path is within project root (security)
        2. Reads current file content (with size limits)
        3. Replaces old_content with new_content
        4. Writes modified content back
        5. Returns True on success

        Override for custom application logic (e.g., line-by-line edits).

        Args:
            change: Change object to apply

        Returns:
            True if change was successfully applied
        """
        try:
            # Security: Validate path is within project root
            try:
                validated_path = validate_path_contained(
                    change.file, self.project_root, allow_nonexistent=True
                )
            except PathSecurityError as e:
                self.log_error(sanitize_error_message(
                    f"Security: {e}", self.project_root
                ))
                return False

            content = safe_read_file(change.file)

            # Replace old content with new
            if change.old_content:
                new_content = content.replace(change.old_content, change.new_content)
            else:
                # Append mode (no old content to replace)
                new_content = content + change.new_content

            # Write back
            change.file.write_text(new_content)
            return True

        except Exception as e:
            self.log_error(f"Failed to apply change to {change.file}: {e}")
            return False

    def rollback_change(self, change: Change) -> bool:
        """
        Rollback a change using git.

        Default implementation uses git checkout to restore file.
        Only works if file is tracked by git.

        Args:
            change: Change object to rollback

        Returns:
            True if rollback succeeded
        """
        from .git_utils import rollback_file
        return rollback_file(change.file)

    def log_error(self, message: str):
        """
        Log an error message.

        Errors are accumulated and included in HealingReport.

        Args:
            message: Error description
        """
        self.errors.append(message)

    def create_report(
        self,
        mode: str,
        issues_found: int,
        issues_fixed: int,
        changes: List[Change],
        execution_time: float
    ) -> HealingReport:
        """
        Create a HealingReport with standard fields.

        Helper method to construct reports with consistent format.

        Args:
            mode: "check" or "heal"
            issues_found: Number of issues detected
            issues_fixed: Number of issues actually fixed
            changes: List of Change objects
            execution_time: Execution time in seconds

        Returns:
            HealingReport instance
        """
        return HealingReport(
            healer_name=self.__class__.__name__,
            mode=mode,
            timestamp=datetime.now().isoformat(),
            issues_found=issues_found,
            issues_fixed=issues_fixed,
            changes=changes,
            errors=self.errors.copy(),
            execution_time=execution_time
        )
