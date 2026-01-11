"""
Atomic file writing utilities.

Prevents file corruption from:
- Ctrl+C interrupts
- Disk full errors
- Power failures

Uses the write-to-temp-then-rename pattern which is atomic on POSIX systems.

Usage:
    from guardian.core.atomic_write import atomic_write, safe_write_text

    # Simple usage
    atomic_write(Path("file.md"), "content")

    # With backup
    safe_write_text(Path("file.md"), "content", backup=True)
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime


class AtomicWriteError(Exception):
    """Error during atomic write operation."""
    pass


def atomic_write(
    file_path: Path,
    content: str,
    encoding: str = 'utf-8',
    backup_dir: Optional[Path] = None
) -> bool:
    """
    Write file atomically to prevent corruption on Ctrl+C or disk full.

    Uses temp file + atomic rename (POSIX guarantee).
    The rename operation is atomic on the same filesystem.

    Args:
        file_path: Path to file to write
        content: Content to write
        encoding: Text encoding (default: utf-8)
        backup_dir: If provided, create backup before overwriting

    Returns:
        True if write succeeded

    Raises:
        AtomicWriteError: If write fails (with descriptive message)
        OSError: If disk is full or permissions issue

    Example:
        >>> atomic_write(Path("docs/guide.md"), "# Guide\n\nContent here")
        True
    """
    file_path = Path(file_path)
    temp_path = None

    try:
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create backup if requested and file exists
        if backup_dir and file_path.exists():
            backup_dir = Path(backup_dir)
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{file_path.name}.{timestamp}.bak"
            shutil.copy2(file_path, backup_path)

        # Write to temp file in same directory (for atomic rename)
        # Using same directory ensures same filesystem
        temp_fd, temp_path_str = tempfile.mkstemp(
            prefix=f".tmp_{file_path.name}_",
            dir=file_path.parent,
            suffix=".tmp"
        )
        temp_path = Path(temp_path_str)

        # Write content to temp file
        try:
            with os.fdopen(temp_fd, 'w', encoding=encoding) as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # Ensure data is on disk
        except OSError as e:
            # Handle specific errors
            if e.errno == 28:  # ENOSPC - No space left on device
                raise AtomicWriteError(
                    f"Disk full: Cannot write to {file_path}. "
                    f"Free up space and try again."
                ) from e
            elif e.errno == 13:  # EACCES - Permission denied
                raise AtomicWriteError(
                    f"Permission denied: Cannot write to {file_path}. "
                    f"Check file/directory permissions."
                ) from e
            else:
                raise AtomicWriteError(
                    f"Write error for {file_path}: {e}"
                ) from e

        # Preserve original file permissions if it exists
        if file_path.exists():
            try:
                original_stat = file_path.stat()
                os.chmod(temp_path, original_stat.st_mode)
            except OSError:
                pass  # Non-critical, continue with default permissions

        # Atomic rename (POSIX guarantee)
        # On Windows, may need to remove target first
        if os.name == 'nt' and file_path.exists():
            os.replace(temp_path, file_path)
        else:
            temp_path.rename(file_path)

        return True

    except AtomicWriteError:
        # Clean up temp file if it exists
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise

    except Exception as e:
        # Clean up temp file on any error
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass

        raise AtomicWriteError(
            f"Failed to write {file_path}: {e}"
        ) from e


def safe_write_text(
    file_path: Path,
    content: str,
    encoding: str = 'utf-8',
    backup: bool = False,
    backup_dir: Optional[Path] = None
) -> bool:
    """
    Safely write text to file with optional backup.

    Higher-level wrapper around atomic_write with sensible defaults.

    Args:
        file_path: Path to file to write
        content: Text content to write
        encoding: Text encoding (default: utf-8)
        backup: If True, create backup before overwriting
        backup_dir: Custom backup directory (default: .doc-guardian/backups)

    Returns:
        True if write succeeded

    Example:
        >>> safe_write_text(Path("README.md"), "# Project\n", backup=True)
        True
    """
    file_path = Path(file_path)

    # Determine backup directory
    if backup and backup_dir is None:
        # Default to .doc-guardian/backups relative to file
        backup_dir = file_path.parent / ".doc-guardian" / "backups"

    return atomic_write(
        file_path,
        content,
        encoding=encoding,
        backup_dir=backup_dir if backup else None
    )


def atomic_replace(
    file_path: Path,
    old_content: str,
    new_content: str,
    encoding: str = 'utf-8',
    backup: bool = True
) -> bool:
    """
    Atomically replace content in a file.

    Reads file, replaces content, writes atomically.
    Creates backup by default.

    Args:
        file_path: Path to file to modify
        old_content: Content to replace
        new_content: Replacement content
        encoding: Text encoding
        backup: Create backup before modifying

    Returns:
        True if replacement was made and file written

    Raises:
        AtomicWriteError: If write fails
        FileNotFoundError: If file doesn't exist
        ValueError: If old_content not found in file
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Read current content
    try:
        current_content = file_path.read_text(encoding=encoding)
    except UnicodeDecodeError as e:
        raise AtomicWriteError(
            f"Cannot read {file_path}: encoding error. "
            f"Try specifying a different encoding."
        ) from e

    # Check if old content exists
    if old_content and old_content not in current_content:
        raise ValueError(
            f"Content to replace not found in {file_path}. "
            f"File may have been modified."
        )

    # Perform replacement
    if old_content:
        modified_content = current_content.replace(old_content, new_content)
    else:
        # Append mode
        modified_content = current_content + new_content

    # Determine backup directory
    backup_dir = None
    if backup:
        backup_dir = file_path.parent / ".doc-guardian" / "backups"

    # Write atomically
    return atomic_write(
        file_path,
        modified_content,
        encoding=encoding,
        backup_dir=backup_dir
    )


def check_write_permissions(file_path: Path) -> Tuple[bool, str]:
    """
    Check if we can write to a file path.

    Args:
        file_path: Path to check

    Returns:
        Tuple of (can_write, reason_if_not)

    Example:
        >>> can_write, reason = check_write_permissions(Path("/etc/hosts"))
        >>> print(can_write, reason)
        False "Permission denied: /etc/hosts"
    """
    file_path = Path(file_path)

    # Check parent directory
    parent = file_path.parent
    if not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return False, f"Cannot create directory: {parent}"
        except OSError as e:
            return False, f"Cannot create directory {parent}: {e}"

    # Check if we can write to parent
    if not os.access(parent, os.W_OK):
        return False, f"Permission denied: {parent}"

    # If file exists, check if we can write to it
    if file_path.exists():
        if not os.access(file_path, os.W_OK):
            return False, f"Permission denied: {file_path}"

    # Check for disk space (rough check)
    try:
        stat = os.statvfs(parent)
        free_space = stat.f_frsize * stat.f_bavail
        if free_space < 1024 * 1024:  # Less than 1MB free
            return False, f"Low disk space: {free_space} bytes free"
    except (OSError, AttributeError):
        pass  # statvfs not available on Windows, skip check

    return True, ""
