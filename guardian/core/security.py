"""
Core security utilities for Doc Guardian.

Provides:
- File size limits to prevent memory exhaustion
- Safe git path handling to prevent command injection
- Module whitelist for context builders
- Centralized security constants

Security fixes for:
- DG-2026-003: Command Injection via Git
- DG-2026-006: Memory Exhaustion
"""

from pathlib import Path
from typing import Tuple, Optional, Set


# ==============================================================================
# Security Constants
# ==============================================================================

# Maximum file size (in bytes) for reading into memory
# Default: 10 MB - should be sufficient for any reasonable documentation
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Maximum number of files to process in a single operation
MAX_FILES_PER_OPERATION = 10000

# Maximum number of content blocks (for duplication detection)
MAX_CONTENT_BLOCKS = 10000

# Maximum number of regex patterns from config
MAX_PATTERNS = 1000

# Maximum number of links to extract from a single file
MAX_LINKS_PER_FILE = 5000

# Allowed modules for context_builder imports (whitelist)
# Only modules in this set can be imported via context_builder config
ALLOWED_CONTEXT_BUILDER_MODULES: Set[str] = {
    # Allow guardian's own modules
    'guardian.core',
    'guardian.core.base',
    'guardian.core.confidence',
    'guardian.core.reporting',
    'guardian.healers',
    # Common safe utilities
    'json',
    'datetime',
    'pathlib',
    'collections',
    'functools',
    'itertools',
    'operator',
    're',
}


# ==============================================================================
# File Size Validation
# ==============================================================================

def validate_file_size(
    file_path: Path,
    max_size: int = MAX_FILE_SIZE_BYTES
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a file is within acceptable size limits.

    Prevents memory exhaustion attacks via large files.

    Args:
        file_path: Path to file to check
        max_size: Maximum allowed size in bytes

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if file is within limits
        - (False, "reason") if file is too large or can't be checked
    """
    try:
        if not file_path.exists():
            return (True, None)  # Non-existent files will fail later anyway

        size = file_path.stat().st_size

        if size > max_size:
            return (
                False,
                f"File too large: {file_path} is {size:,} bytes "
                f"(max: {max_size:,} bytes)"
            )

        return (True, None)

    except Exception as e:
        return (False, f"Cannot check file size for {file_path}: {e}")


def safe_read_file(
    file_path: Path,
    max_size: int = MAX_FILE_SIZE_BYTES,
    encoding: str = 'utf-8'
) -> str:
    """
    Safely read a file with size limits.

    Args:
        file_path: Path to file to read
        max_size: Maximum allowed size in bytes
        encoding: File encoding

    Returns:
        File contents as string

    Raises:
        ValueError: If file is too large
        OSError: If file cannot be read
    """
    is_valid, error = validate_file_size(file_path, max_size)
    if not is_valid:
        raise ValueError(error)

    return file_path.read_text(encoding=encoding)


def safe_read_bytes(
    file_path: Path,
    max_size: int = MAX_FILE_SIZE_BYTES
) -> bytes:
    """
    Safely read a file as bytes with size limits.

    Args:
        file_path: Path to file to read
        max_size: Maximum allowed size in bytes

    Returns:
        File contents as bytes

    Raises:
        ValueError: If file is too large
        OSError: If file cannot be read
    """
    is_valid, error = validate_file_size(file_path, max_size)
    if not is_valid:
        raise ValueError(error)

    return file_path.read_bytes()


# ==============================================================================
# Git Path Safety
# ==============================================================================

def safe_git_path(path: Path) -> str:
    """
    Make a path safe for use in git commands.

    Prevents command injection via malicious filenames that start with '-'
    which could be interpreted as git options.

    Args:
        path: Path to make safe

    Returns:
        Safe path string for git commands
    """
    path_str = str(path)

    # Prefix with ./ if path starts with - to prevent option injection
    if path_str.startswith('-'):
        return './' + path_str

    return path_str


def validate_git_path(path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate that a path is safe for git operations.

    Args:
        path: Path to validate

    Returns:
        Tuple of (is_safe, error_message)
    """
    path_str = str(path)

    # Check for null bytes (could cause issues)
    if '\x00' in path_str:
        return (False, "Path contains null byte")

    # Check for very long paths (potential buffer issues)
    if len(path_str) > 4096:
        return (False, "Path is excessively long")

    return (True, None)


# ==============================================================================
# Module Whitelist Validation
# ==============================================================================

def validate_module_path(
    module_path: str,
    allowed_modules: Optional[Set[str]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a module path is in the allowed whitelist.

    Prevents arbitrary code execution via malicious context_builder config.

    Args:
        module_path: Dotted module path (e.g., "myproject.utils.build_context")
        allowed_modules: Set of allowed module prefixes (uses default if None)

    Returns:
        Tuple of (is_allowed, error_message)
    """
    if allowed_modules is None:
        allowed_modules = ALLOWED_CONTEXT_BUILDER_MODULES

    # Extract the module part (everything before the last dot)
    if '.' not in module_path:
        # Single name - must be in allowed list exactly
        if module_path in allowed_modules:
            return (True, None)
        return (
            False,
            f"Module '{module_path}' is not in the allowed whitelist. "
            f"Allowed modules: {sorted(allowed_modules)}"
        )

    # Check if any allowed module is a prefix of the module path
    for allowed in allowed_modules:
        if module_path == allowed or module_path.startswith(allowed + '.'):
            return (True, None)

    return (
        False,
        f"Module '{module_path}' is not in the allowed whitelist. "
        f"Allowed module prefixes: {sorted(allowed_modules)}"
    )


# ==============================================================================
# Collection Size Limits
# ==============================================================================

def check_collection_size(
    collection,
    max_size: int,
    collection_name: str = "collection"
) -> Tuple[bool, Optional[str]]:
    """
    Check if a collection is within size limits.

    Args:
        collection: Collection to check (must support len())
        max_size: Maximum allowed size
        collection_name: Name for error messages

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        size = len(collection)
        if size > max_size:
            return (
                False,
                f"Too many items in {collection_name}: {size:,} > {max_size:,}"
            )
        return (True, None)
    except TypeError:
        return (False, f"Cannot determine size of {collection_name}")


def enforce_collection_limit(
    collection,
    max_size: int,
    collection_name: str = "collection"
):
    """
    Enforce collection size limit, raising error if exceeded.

    Args:
        collection: Collection to check
        max_size: Maximum allowed size
        collection_name: Name for error messages

    Raises:
        MemoryError: If collection exceeds limit
    """
    is_valid, error = check_collection_size(collection, max_size, collection_name)
    if not is_valid:
        raise MemoryError(error)


# ==============================================================================
# Error Message Sanitization
# ==============================================================================

def sanitize_error_message(
    message: str,
    project_root: Optional[Path] = None
) -> str:
    """
    Sanitize error message to avoid leaking sensitive path information.

    Args:
        message: Error message to sanitize
        project_root: If provided, replace absolute paths with relative ones

    Returns:
        Sanitized error message
    """
    if project_root:
        # Replace absolute paths with relative ones
        root_str = str(project_root.resolve())
        message = message.replace(root_str, '<project>')

    # Remove any home directory references
    import os
    home = os.path.expanduser('~')
    if home and home != '~':
        message = message.replace(home, '<home>')

    return message
