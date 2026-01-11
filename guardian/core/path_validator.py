"""
Path validator for preventing path traversal attacks.

Ensures all file paths are within allowed directories and don't use
directory traversal techniques (../, symlinks, etc.).
"""

from pathlib import Path
from typing import List, Optional, Set
import os


class PathTraversalError(Exception):
    """Raised when path traversal attempt is detected."""
    pass


class PathValidator:
    """Validates file paths for security issues."""

    def __init__(self, allowed_roots: List[Path], follow_symlinks: bool = False):
        """
        Initialize path validator.

        Args:
            allowed_roots: List of root directories that are allowed
            follow_symlinks: Whether to allow symlinks (default: False for security)
        """
        # Resolve all roots to absolute paths
        self.allowed_roots = [Path(root).resolve() for root in allowed_roots]
        self.follow_symlinks = follow_symlinks

    def validate_path(self, path: Path, purpose: str = "") -> Path:
        """
        Validate a path for security issues.

        Args:
            path: Path to validate
            purpose: Optional description of what this path is for

        Returns:
            Resolved absolute path if valid

        Raises:
            PathTraversalError: If path is invalid or outside allowed roots
        """
        # Convert to Path object if string
        if isinstance(path, str):
            path = Path(path)

        # Check for null bytes (common in attacks)
        if '\x00' in str(path):
            raise PathTraversalError(f"Path contains null byte: {path}")

        # Resolve to absolute path
        try:
            resolved_path = path.resolve()
        except (OSError, RuntimeError) as e:
            raise PathTraversalError(f"Failed to resolve path {path}: {e}")

        # Check symlinks
        if not self.follow_symlinks and path.is_symlink():
            raise PathTraversalError(f"Symlinks not allowed: {path}")

        # Check if path is within allowed roots
        is_allowed = False
        for root in self.allowed_roots:
            try:
                # Check if resolved path is relative to allowed root
                resolved_path.relative_to(root)
                is_allowed = True
                break
            except ValueError:
                # Not relative to this root, try next
                continue

        if not is_allowed:
            roots_str = ", ".join(str(r) for r in self.allowed_roots)
            raise PathTraversalError(
                f"Path {resolved_path} is outside allowed roots: {roots_str}"
            )

        return resolved_path

    def validate_paths(self, paths: List[Path]) -> List[Path]:
        """
        Validate multiple paths.

        Args:
            paths: List of paths to validate

        Returns:
            List of validated paths

        Raises:
            PathTraversalError: If any path is invalid
        """
        return [self.validate_path(path) for path in paths]

    def is_safe_filename(self, filename: str) -> bool:
        """
        Check if a filename is safe (no path components).

        Args:
            filename: Filename to check

        Returns:
            True if safe, False otherwise
        """
        # Check for path separators
        if os.sep in filename or (os.altsep and os.altsep in filename):
            return False

        # Check for parent directory reference
        if filename in ('.', '..'):
            return False

        # Check for null bytes
        if '\x00' in filename:
            return False

        return True

    def get_safe_subpath(self, root: Path, subpath: str) -> Path:
        """
        Safely join a root with a subpath, validating result.

        Args:
            root: Root directory
            subpath: Relative path to join

        Returns:
            Validated full path

        Raises:
            PathTraversalError: If result is invalid
        """
        full_path = root / subpath
        return self.validate_path(full_path)


def create_doc_path_validator(project_root: Path, doc_root: Path) -> PathValidator:
    """
    Create a path validator for documentation files.

    Args:
        project_root: Project root directory
        doc_root: Documentation root directory

    Returns:
        Configured PathValidator
    """
    allowed_roots = [project_root, doc_root]
    return PathValidator(allowed_roots=allowed_roots, follow_symlinks=False)


def validate_file_path(path: Path, allowed_roots: List[Path]) -> bool:
    """
    Quick validation function.

    Args:
        path: Path to validate
        allowed_roots: List of allowed root directories

    Returns:
        True if path is valid, False otherwise
    """
    try:
        validator = PathValidator(allowed_roots)
        validator.validate_path(path)
        return True
    except PathTraversalError:
        return False


# Alias for backward compatibility with base.py
PathSecurityError = PathTraversalError


def validate_path_contained(path: Path, container: Path, allow_nonexistent: bool = False) -> Path:
    """
    Validate that a path is contained within a container directory.

    Args:
        path: Path to validate
        container: Container directory
        allow_nonexistent: If True, allow paths that don't exist yet

    Returns:
        Resolved absolute path if valid (or logical path if allow_nonexistent=True)

    Raises:
        PathSecurityError: If path is outside container
    """
    if not isinstance(path, Path):
        path = Path(path)
    if not isinstance(container, Path):
        container = Path(container)

    # Resolve container to absolute path
    try:
        resolved_container = container.resolve()
    except (OSError, RuntimeError) as e:
        raise PathSecurityError(f"Invalid container {container}: {e}")

    # For nonexistent paths, check if the logical path would be inside container
    if allow_nonexistent and not path.exists():
        # Make path absolute if relative
        if not path.is_absolute():
            logical_path = (resolved_container / path).resolve()
        else:
            logical_path = path.resolve()

        # Check if it's within container
        try:
            logical_path.relative_to(resolved_container)
            return logical_path
        except ValueError:
            raise PathSecurityError(
                f"Path {logical_path} is outside container {resolved_container}"
            )

    # For existing paths, use standard validation
    validator = PathValidator(allowed_roots=[container])
    return validator.validate_path(path)


def validate_project_root(root: Path) -> Path:
    """
    Validate that a project root exists and is accessible.

    Args:
        root: Project root path

    Returns:
        Resolved absolute path

    Raises:
        PathSecurityError: If root is invalid
    """
    if not isinstance(root, Path):
        root = Path(root)

    try:
        resolved = root.resolve()
    except (OSError, RuntimeError) as e:
        raise PathSecurityError(f"Invalid project root {root}: {e}")

    if not resolved.exists():
        raise PathSecurityError(f"Project root does not exist: {resolved}")

    if not resolved.is_dir():
        raise PathSecurityError(f"Project root is not a directory: {resolved}")

    return resolved


def validate_doc_root(doc_root: Path, project_root: Path) -> Path:
    """
    Validate that a doc root is contained within project root.

    Args:
        doc_root: Documentation root path
        project_root: Project root path

    Returns:
        Resolved absolute path

    Raises:
        PathSecurityError: If doc root is invalid or outside project root
    """
    if not isinstance(doc_root, Path):
        doc_root = Path(doc_root)

    try:
        resolved = doc_root.resolve()
    except (OSError, RuntimeError) as e:
        raise PathSecurityError(f"Invalid doc root {doc_root}: {e}")

    # Validate it's within project root
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError:
        raise PathSecurityError(
            f"Doc root {resolved} is outside project root {project_root}"
        )

    return resolved


def validate_templates_dir(templates_dir: Path, project_root: Path) -> Path:
    """
    Validate that a templates directory is contained within project root.

    Args:
        templates_dir: Templates directory path
        project_root: Project root path

    Returns:
        Resolved absolute path

    Raises:
        PathSecurityError: If templates dir is invalid or outside project root
    """
    if not isinstance(templates_dir, Path):
        templates_dir = Path(templates_dir)

    try:
        resolved = templates_dir.resolve()
    except (OSError, RuntimeError) as e:
        raise PathSecurityError(f"Invalid templates directory {templates_dir}: {e}")

    # Validate it's within project root
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError:
        raise PathSecurityError(
            f"Templates directory {resolved} is outside project root {project_root}"
        )

    return resolved
