"""
Comprehensive logging for Doc Guardian.

Provides structured logging with:
- Console output (colorized if supported)
- File output (JSON format for parsing)
- Context tracking (healer name, file being processed)
- Error categorization

Usage:
    from guardian.core.logger import setup_logger, get_logger

    # Setup at start
    logger = setup_logger("doc-guardian", log_file=Path("guardian.log"))

    # Use throughout
    logger.info("Processing file", extra={"file": "README.md"})
    logger.error("File not found", extra={"file": "missing.md", "error_code": "FS-06"})
"""

import logging
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict


# Error codes from the audit
ERROR_CODES = {
    # File System Errors
    "FS-01": "Read-only directory",
    "FS-03": "Disk full",
    "FS-04": "File locked",
    "FS-05": "Symlink loop",
    "FS-06": "File deleted during processing",
    "FS-07": "File modified during processing",
    "FS-09": "Path too long",
    "FS-10": "Network drive disconnect",
    "FS-14": "Doc root does not exist",

    # Git Errors
    "GIT-03": "Merge conflict in progress",
    "GIT-04": "Git not installed",
    "GIT-06": "Git timeout",
    "GIT-07": "Untracked file rollback",
    "GIT-08": "Git hook rejection",
    "GIT-10": "Concurrent git operation",

    # Runtime Errors
    "RT-01": "Out of memory",
    "RT-04": "Regex timeout (ReDoS)",
    "RT-06": "Keyboard interrupt",
    "RT-07": "SIGTERM received",

    # Data/Content Errors
    "DC-04": "Null bytes in file",
    "DC-05": "File too large",
    "DC-07": "Malformed JSON",
    "DC-10": "Extremely long line",

    # Configuration Errors
    "CFG-04": "Invalid confidence threshold",
    "CFG-05": "Invalid regex in config",
}


@dataclass
class LogContext:
    """Context information for log entries."""
    healer_name: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    error_code: Optional[str] = None
    operation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class ContextFilter(logging.Filter):
    """Add context information to log records."""

    def __init__(self, default_context: Optional[LogContext] = None):
        super().__init__()
        self.context = default_context or LogContext()

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context attributes to record."""
        # Add context from filter
        for key, value in self.context.to_dict().items():
            if not hasattr(record, key):
                setattr(record, key, value)

        # Ensure all context fields exist
        for field in ['healer_name', 'file_path', 'line_number', 'error_code', 'operation']:
            if not hasattr(record, field):
                setattr(record, field, None)

        return True


class ColoredFormatter(logging.Formatter):
    """Colorized console formatter."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m',
    }

    ICONS = {
        'DEBUG': '🔍',
        'INFO': '✅',
        'WARNING': '⚠️ ',
        'ERROR': '❌',
        'CRITICAL': '🚨',
    }

    def __init__(self, use_colors: bool = True, use_icons: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()
        self.use_icons = use_icons

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors and icons."""
        level = record.levelname
        icon = self.ICONS.get(level, '') if self.use_icons else ''

        # Build message
        parts = []

        if icon:
            parts.append(icon)

        if self.use_colors:
            color = self.COLORS.get(level, '')
            reset = self.COLORS['RESET']
            parts.append(f"{color}{level}{reset}")
        else:
            parts.append(level)

        # Add context if present
        context_parts = []
        if hasattr(record, 'healer_name') and record.healer_name:
            context_parts.append(f"[{record.healer_name}]")
        if hasattr(record, 'file_path') and record.file_path:
            file_info = record.file_path
            if hasattr(record, 'line_number') and record.line_number:
                file_info += f":{record.line_number}"
            context_parts.append(f"({file_info})")

        if context_parts:
            parts.append(' '.join(context_parts))

        parts.append(record.getMessage())

        # Add error code if present
        if hasattr(record, 'error_code') and record.error_code:
            error_desc = ERROR_CODES.get(record.error_code, "Unknown error")
            parts.append(f"[{record.error_code}: {error_desc}]")

        return ' '.join(parts)


class JSONFormatter(logging.Formatter):
    """JSON formatter for file logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name,
        }

        # Add context fields
        for field in ['healer_name', 'file_path', 'line_number', 'error_code', 'operation']:
            if hasattr(record, field) and getattr(record, field) is not None:
                log_entry[field] = getattr(record, field)

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logger(
    name: str = "doc-guardian",
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
    console: bool = True,
    use_colors: bool = True,
    use_icons: bool = True
) -> logging.Logger:
    """
    Setup logger with file and console output.

    Args:
        name: Logger name
        log_file: Path to log file (JSON format)
        level: Logging level
        console: Enable console output
        use_colors: Use ANSI colors in console
        use_icons: Use emoji icons in console

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logger("doc-guardian", log_file=Path("heal.log"))
        >>> logger.info("Starting healing", extra={"healer_name": "fix_broken_links"})
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    # Add context filter
    context_filter = ContextFilter()
    logger.addFilter(context_filter)

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(ColoredFormatter(use_colors, use_icons))
        logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "doc-guardian") -> logging.Logger:
    """
    Get existing logger or create new one.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class HealerLogger:
    """
    Logger wrapper for healers with automatic context.

    Provides convenient methods that automatically include healer context.
    """

    def __init__(self, healer_name: str, logger: Optional[logging.Logger] = None):
        """
        Initialize healer logger.

        Args:
            healer_name: Name of the healer
            logger: Optional base logger (uses default if not provided)
        """
        self.healer_name = healer_name
        self._logger = logger or get_logger()

    def _log(
        self,
        level: int,
        message: str,
        file_path: Optional[Path] = None,
        line_number: Optional[int] = None,
        error_code: Optional[str] = None,
        **kwargs
    ):
        """Internal log method with context."""
        extra = {
            'healer_name': self.healer_name,
            'file_path': str(file_path) if file_path else None,
            'line_number': line_number,
            'error_code': error_code,
            **kwargs
        }
        self._logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log(logging.CRITICAL, message, **kwargs)

    def file_error(
        self,
        message: str,
        file_path: Path,
        line_number: Optional[int] = None,
        error_code: Optional[str] = None
    ):
        """
        Log file-related error with context.

        Args:
            message: Error message
            file_path: Path to file
            line_number: Line number (if applicable)
            error_code: Error code from ERROR_CODES
        """
        self.error(
            message,
            file_path=file_path,
            line_number=line_number,
            error_code=error_code
        )

    def operation_start(self, operation: str, file_path: Optional[Path] = None):
        """Log start of an operation."""
        self.debug(
            f"Starting: {operation}",
            file_path=file_path,
            operation=operation
        )

    def operation_complete(
        self,
        operation: str,
        file_path: Optional[Path] = None,
        success: bool = True
    ):
        """Log completion of an operation."""
        if success:
            self.debug(f"Completed: {operation}", file_path=file_path)
        else:
            self.warning(f"Failed: {operation}", file_path=file_path)
