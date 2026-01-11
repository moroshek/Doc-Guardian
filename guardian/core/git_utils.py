"""
Git integration utilities for healing operations.

Provides safe git operations for:
- Rolling back files
- Committing changes
- Checking repository status

Error handling features:
- Detailed error messages for git operations (GIT-04, GIT-06, GIT-07)
- Timeout handling (GIT-06)
- Proper error propagation

Security features:
- Safe path handling to prevent command injection (DG-2026-003)
"""

import subprocess
import shutil
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from .security import safe_git_path, validate_git_path


# Get module logger
logger = logging.getLogger(__name__)


class GitError(Exception):
    """Base exception for git-related errors."""
    pass


class GitNotInstalledError(GitError):
    """Git is not installed or not in PATH (GIT-04)."""
    pass


class GitTimeoutError(GitError):
    """Git operation timed out (GIT-06)."""
    pass


class GitMergeConflictError(GitError):
    """Git merge conflict in progress (GIT-03)."""
    pass


class GitHookRejectionError(GitError):
    """Git hook rejected the operation (GIT-08)."""
    pass


class GitRollbackError(GitError):
    """Cannot rollback untracked file (GIT-07)."""
    pass


def _check_git_installed() -> bool:
    """
    Check if git is installed and accessible.

    Returns:
        True if git is available, False otherwise
    """
    return shutil.which('git') is not None


def _run_git_command(
    cmd: List[str],
    cwd: Path,
    timeout: int = 30,
    operation_name: str = "git operation"
) -> Tuple[bool, str, str]:
    """
    Run a git command with proper error handling.

    Args:
        cmd: Command list to run
        cwd: Working directory
        timeout: Timeout in seconds
        operation_name: Description of operation for error messages

    Returns:
        Tuple of (success, stdout, stderr)

    Raises:
        GitNotInstalledError: If git is not installed (GIT-04)
        GitTimeoutError: If command times out (GIT-06)
    """
    if not _check_git_installed():
        raise GitNotInstalledError(
            "Git is not installed or not in PATH. "
            "Install git: https://git-scm.com/downloads"
        )

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired as e:
        msg = f"Git {operation_name} timed out after {timeout}s. The repository may be large or network issues occurred."
        logger.error(msg)
        raise GitTimeoutError(msg) from e
    except FileNotFoundError as e:
        raise GitNotInstalledError(f"Git command not found: {e}") from e
    except PermissionError as e:
        msg = f"Permission denied executing git: {e}"
        logger.error(msg)
        return False, "", msg


def rollback_file(file_path: Path) -> bool:
    """
    Rollback a file to HEAD using git checkout.

    Only works if:
    1. File is in a git repository
    2. File is tracked by git
    3. Git is available

    Security: Uses safe_git_path to prevent command injection via
    filenames starting with '-'.

    Args:
        file_path: Path to file to rollback

    Returns:
        True if rollback succeeded, False otherwise

    Raises:
        GitNotInstalledError: If git is not installed (GIT-04)
        GitTimeoutError: If operation times out (GIT-06)
        GitRollbackError: If file is untracked (GIT-07)
    """
    if not file_path.exists():
        logger.warning(f"Cannot rollback non-existent file: {file_path}")
        return False

    # Security: Validate git path
    is_valid, error = validate_git_path(file_path)
    if not is_valid:
        logger.warning(f"Invalid git path: {error}")
        return False

    # Check if file is tracked
    try:
        success, stdout, stderr = _run_git_command(
            ['git', 'ls-files', '--error-unmatch', '--', safe_git_path(file_path)],
            cwd=file_path.parent,
            timeout=10,
            operation_name="check tracked status"
        )
        if not success:
            msg = f"Cannot rollback untracked file: {file_path}. Add it to git first or delete manually."
            logger.warning(msg)
            raise GitRollbackError(msg)
    except GitError:
        raise

    # Perform rollback
    try:
        success, stdout, stderr = _run_git_command(
            ['git', 'checkout', 'HEAD', '--', safe_git_path(file_path)],
            cwd=file_path.parent,
            timeout=10,
            operation_name="checkout"
        )

        if not success:
            logger.error(f"Git rollback failed for {file_path}: {stderr}")

        return success
    except GitError:
        raise


def git_add(file_path: Path) -> bool:
    """
    Stage a file for commit.

    Security: Uses safe_git_path to prevent command injection.

    Args:
        file_path: Path to file to stage

    Returns:
        True if staging succeeded

    Raises:
        GitNotInstalledError: If git is not installed (GIT-04)
        GitTimeoutError: If operation times out (GIT-06)
    """
    if not file_path.exists():
        logger.warning(f"Cannot stage non-existent file: {file_path}")
        return False

    # Security: Validate git path
    is_valid, error = validate_git_path(file_path)
    if not is_valid:
        logger.warning(f"Invalid git path for staging: {error}")
        return False

    try:
        success, stdout, stderr = _run_git_command(
            ['git', 'add', '--', safe_git_path(file_path)],
            cwd=file_path.parent,
            timeout=10,
            operation_name="add"
        )

        if not success:
            logger.error(f"Failed to stage {file_path}: {stderr}")

        return success
    except GitError:
        raise


def git_commit(message: str, files: List[Path], repo_root: Optional[Path] = None) -> bool:
    """
    Git commit with standard format.

    Args:
        message: Commit message (should follow conventional commits format)
        files: List of files to commit (will be staged first)
        repo_root: Repository root (uses first file's parent if not provided)

    Returns:
        True if commit succeeded

    Raises:
        GitNotInstalledError: If git is not installed (GIT-04)
        GitTimeoutError: If operation times out (GIT-06)
        GitHookRejectionError: If pre-commit hook rejects (GIT-08)
        GitMergeConflictError: If merge conflict exists (GIT-03)

    Example:
        >>> files = [Path("docs/guide.md"), Path("docs/tutorial.md")]
        >>> git_commit("docs: fix broken links", files)
        True
    """
    if not files:
        logger.warning("No files provided for commit")
        return False

    cwd = repo_root or files[0].parent

    # Check for merge conflict first (GIT-03)
    try:
        success, stdout, stderr = _run_git_command(
            ['git', 'status', '--porcelain'],
            cwd=cwd,
            timeout=10,
            operation_name="status check"
        )
        if 'UU ' in stdout or 'AA ' in stdout or 'DD ' in stdout:
            msg = "Cannot commit: merge conflict in progress. Resolve conflicts first."
            logger.error(msg)
            raise GitMergeConflictError(msg)
    except GitError:
        raise

    try:
        # Stage all files first
        for file_path in files:
            if not git_add(file_path):
                return False

        # Commit
        success, stdout, stderr = _run_git_command(
            ['git', 'commit', '-m', message],
            cwd=cwd,
            timeout=30,
            operation_name="commit"
        )

        if not success:
            # Check for hook rejection (GIT-08)
            if 'hook' in stderr.lower() or 'pre-commit' in stderr.lower():
                msg = f"Commit rejected by git hook: {stderr}"
                logger.error(msg)
                raise GitHookRejectionError(msg)

            logger.error(f"Git commit failed: {stderr}")

        return success
    except GitError:
        raise


def git_status_clean(repo_root: Path) -> bool:
    """
    Check if git working directory is clean.

    Args:
        repo_root: Path to git repository root

    Returns:
        True if no uncommitted changes, False otherwise

    Raises:
        GitNotInstalledError: If git is not installed (GIT-04)
        GitTimeoutError: If operation times out (GIT-06)
    """
    try:
        success, stdout, stderr = _run_git_command(
            ['git', 'status', '--porcelain'],
            cwd=repo_root,
            timeout=10,
            operation_name="status"
        )
        return success and not stdout.strip()
    except GitError:
        raise


def git_diff(file_path: Path, staged: bool = False) -> Optional[str]:
    """
    Get git diff for a file.

    Security: Uses safe_git_path to prevent command injection.

    Args:
        file_path: Path to file
        staged: If True, get diff of staged changes (--cached)

    Returns:
        Diff output as string, or None if error

    Raises:
        GitNotInstalledError: If git is not installed (GIT-04)
        GitTimeoutError: If operation times out (GIT-06)
    """
    # Security: Validate git path
    is_valid, error = validate_git_path(file_path)
    if not is_valid:
        logger.warning(f"Invalid git path for diff: {error}")
        return None

    try:
        cmd = ['git', 'diff']
        if staged:
            cmd.append('--cached')
        cmd.extend(['--', safe_git_path(file_path)])

        success, stdout, stderr = _run_git_command(
            cmd,
            cwd=file_path.parent,
            timeout=10,
            operation_name="diff"
        )

        if success:
            return stdout

        logger.warning(f"Git diff failed for {file_path}: {stderr}")
        return None
    except GitError:
        raise


def is_git_repo(path: Path) -> bool:
    """
    Check if path is inside a git repository.

    Args:
        path: Path to check

    Returns:
        True if inside git repo
    """
    if not _check_git_installed():
        return False

    try:
        success, stdout, stderr = _run_git_command(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=path if path.is_dir() else path.parent,
            timeout=5,
            operation_name="repo check"
        )
        return success and stdout.strip() == 'true'
    except GitError:
        return False


def check_merge_conflict(repo_root: Path) -> bool:
    """
    Check if there is a merge conflict in progress (GIT-03).

    Args:
        repo_root: Path to repository root

    Returns:
        True if merge conflict exists
    """
    try:
        merge_head = repo_root / '.git' / 'MERGE_HEAD'
        return merge_head.exists()
    except Exception:
        return False
