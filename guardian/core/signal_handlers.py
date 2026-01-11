"""
Signal handlers for graceful shutdown.

Handles Ctrl+C (SIGINT) and SIGTERM gracefully to:
- Prevent corrupted file states
- Run cleanup actions
- Provide clear shutdown messages

Usage:
    from guardian.core.signal_handlers import GracefulShutdown, shutdown_manager

    # Register cleanup action
    shutdown_manager.register_cleanup(lambda: print("Cleaning up..."))

    # Check if shutdown was requested
    if shutdown_manager.shutdown_requested:
        # Stop processing
        pass
"""

import signal
import sys
import atexit
from pathlib import Path
from typing import Callable, List, Optional
from contextlib import contextmanager


class GracefulShutdown:
    """
    Handle Ctrl+C (SIGINT) and SIGTERM gracefully.

    Prevents data corruption by:
    1. Catching interrupt signals
    2. Running registered cleanup actions
    3. Allowing in-progress operations to complete safely
    """

    def __init__(self):
        """Initialize graceful shutdown handler."""
        self.shutdown_requested = False
        self.cleanup_actions: List[Callable[[], None]] = []
        self._original_sigint = None
        self._original_sigterm = None
        self._installed = False
        self._in_progress_files: List[Path] = []

    def install(self):
        """
        Install signal handlers.

        Call this at the start of the main program to enable
        graceful shutdown handling.
        """
        if self._installed:
            return

        # Save original handlers
        self._original_sigint = signal.signal(signal.SIGINT, self._signal_handler)
        self._original_sigterm = signal.signal(signal.SIGTERM, self._signal_handler)

        # Register atexit handler for normal exit cleanup
        atexit.register(self._atexit_cleanup)

        self._installed = True

    def uninstall(self):
        """
        Restore original signal handlers.

        Call this when done with graceful shutdown handling.
        """
        if not self._installed:
            return

        # Restore original handlers
        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm)

        self._installed = False

    def _signal_handler(self, signum: int, frame):
        """
        Handle interrupt signals.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        print(f"\n⚠️  Shutdown requested ({signal_name}). Cleaning up...")

        self.shutdown_requested = True

        # Run cleanup actions
        self._run_cleanup()

        # Exit cleanly
        sys.exit(128 + signum)

    def _atexit_cleanup(self):
        """Run cleanup on normal exit."""
        if self._in_progress_files:
            print(f"⚠️  Cleaning up {len(self._in_progress_files)} in-progress files...")
        self._run_cleanup()

    def _run_cleanup(self):
        """Run all registered cleanup actions."""
        for action in self.cleanup_actions:
            try:
                action()
            except Exception as e:
                print(f"   Cleanup error: {e}")

        # Clean up any in-progress temp files
        for temp_file in self._in_progress_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    print(f"   Removed incomplete: {temp_file}")
            except Exception as e:
                print(f"   Failed to remove {temp_file}: {e}")

        self._in_progress_files.clear()

    def register_cleanup(self, action: Callable[[], None]):
        """
        Register a cleanup action for shutdown.

        Args:
            action: Callable to run on shutdown (no arguments, no return)

        Example:
            >>> shutdown.register_cleanup(lambda: print("Goodbye!"))
        """
        self.cleanup_actions.append(action)

    def unregister_cleanup(self, action: Callable[[], None]):
        """
        Remove a cleanup action.

        Args:
            action: Callable previously registered
        """
        if action in self.cleanup_actions:
            self.cleanup_actions.remove(action)

    def register_in_progress_file(self, file_path: Path):
        """
        Register a file currently being written.

        If shutdown occurs, these files will be cleaned up.

        Args:
            file_path: Path to file being written
        """
        self._in_progress_files.append(file_path)

    def unregister_in_progress_file(self, file_path: Path):
        """
        Unregister a file after successful write.

        Args:
            file_path: Path to file that was successfully written
        """
        if file_path in self._in_progress_files:
            self._in_progress_files.remove(file_path)

    @contextmanager
    def protected_write(self, file_path: Path):
        """
        Context manager for protected file writes.

        Automatically registers/unregisters files for cleanup.

        Usage:
            with shutdown.protected_write(Path("file.md")):
                file.write_text(content)

        Args:
            file_path: Path to file being written
        """
        self.register_in_progress_file(file_path)
        try:
            yield
        finally:
            self.unregister_in_progress_file(file_path)

    def check_shutdown(self) -> bool:
        """
        Check if shutdown was requested.

        Use this in long-running loops to exit gracefully.

        Returns:
            True if shutdown was requested, False otherwise

        Example:
            for file in files:
                if shutdown.check_shutdown():
                    break
                process_file(file)
        """
        return self.shutdown_requested


# Global instance for convenience
shutdown_manager = GracefulShutdown()


def install_signal_handlers():
    """
    Install global signal handlers.

    Call this at the start of the main program.
    """
    shutdown_manager.install()


def is_shutdown_requested() -> bool:
    """
    Check if shutdown was requested.

    Convenience function for checking shutdown status.

    Returns:
        True if shutdown was requested
    """
    return shutdown_manager.shutdown_requested
