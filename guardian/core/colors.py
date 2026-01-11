"""
Terminal color utilities for Doc Guardian.

Provides ANSI color codes and formatting helpers for improved UX.
No external dependencies - uses standard ANSI escape codes.

Security: Only outputs to TTY (checks sys.stdout.isatty())
"""

import sys


class Colors:
    """ANSI color codes for terminal output."""
    # Basic colors
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

    # Text formatting
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'

    # Reset
    RESET = '\033[0m'

    # Combinations
    BOLD_RED = '\033[1;91m'
    BOLD_GREEN = '\033[1;92m'
    BOLD_YELLOW = '\033[1;93m'
    BOLD_BLUE = '\033[1;94m'


def colorize(text: str, color: str) -> str:
    """
    Add color to text if stdout is a TTY.

    Args:
        text: Text to colorize
        color: ANSI color code from Colors class

    Returns:
        Colored text if TTY, plain text otherwise
    """
    if sys.stdout.isatty():
        return f"{color}{text}{Colors.RESET}"
    return text


def success(text: str) -> str:
    """Format text as success (green)."""
    return colorize(text, Colors.GREEN)


def error(text: str) -> str:
    """Format text as error (red)."""
    return colorize(text, Colors.RED)


def warning(text: str) -> str:
    """Format text as warning (yellow)."""
    return colorize(text, Colors.YELLOW)


def info(text: str) -> str:
    """Format text as info (blue)."""
    return colorize(text, Colors.BLUE)


def bold(text: str) -> str:
    """Format text as bold."""
    return colorize(text, Colors.BOLD)


def dim(text: str) -> str:
    """Format text as dim."""
    return colorize(text, Colors.DIM)


def show_progress(current: int, total: int, prefix: str = "", bar_length: int = 40):
    """
    Display progress bar for file processing.

    Only displays if stdout is a TTY (no progress spam in logs).
    Uses carriage return to update in place.

    Args:
        current: Current progress count
        total: Total items to process
        prefix: Text to show before progress bar
        bar_length: Length of progress bar in characters

    Example:
        for i in range(100):
            show_progress(i+1, 100, "Processing")
    """
    if not sys.stdout.isatty():
        return

    percent = (current / total) * 100 if total > 0 else 0
    filled = int(bar_length * current / total) if total > 0 else 0
    bar = '█' * filled + '░' * (bar_length - filled)

    # Format with color
    if percent == 100:
        bar_color = Colors.GREEN
    elif percent >= 50:
        bar_color = Colors.BLUE
    else:
        bar_color = Colors.YELLOW

    print(
        f"\r{prefix} {colorize(f'|{bar}|', bar_color)} {current}/{total} ({percent:.1f}%)",
        end='',
        flush=True
    )

    # Print newline when complete
    if current == total:
        print()


def clear_progress():
    """Clear progress bar line (for error handling)."""
    if sys.stdout.isatty():
        print('\r' + ' ' * 100 + '\r', end='', flush=True)


def print_box(lines: list, title: str = "", width: int = 60):
    """
    Print text in a bordered box.

    Args:
        lines: List of strings to print inside box
        title: Optional title for top of box
        width: Width of box in characters

    Example:
        print_box([
            "✓ Fixed 21/28 issues",
            "⚠ 7 issues need manual review"
        ], title="Summary")
    """
    # Box drawing characters
    top_left = '╭'
    top_right = '╮'
    bottom_left = '╰'
    bottom_right = '╯'
    horizontal = '─'
    vertical = '│'

    # Top border
    if title:
        title_text = f" {title} "
        padding = (width - len(title_text) - 2) // 2
        top_line = (
            top_left + horizontal * padding +
            title_text +
            horizontal * (width - len(title_text) - padding - 1) +
            top_right
        )
    else:
        top_line = top_left + horizontal * (width - 2) + top_right

    print(colorize(top_line, Colors.BOLD))

    # Content lines
    print(colorize(vertical, Colors.BOLD) + ' ' * (width - 2) + colorize(vertical, Colors.BOLD))
    for line in lines:
        # Strip ANSI codes for length calculation
        clean_line = line
        for color in [Colors.RED, Colors.GREEN, Colors.YELLOW, Colors.BLUE,
                     Colors.BOLD, Colors.RESET, Colors.DIM]:
            clean_line = clean_line.replace(color, '')

        # Truncate lines that exceed box width (with room for borders and padding)
        max_content_width = width - 6
        if len(clean_line) > max_content_width:
            # Truncate the display line, preserving ANSI codes where possible
            truncate_at = max_content_width - 3  # Room for "..."
            # Simple truncation - just cut at position (may break mid-ANSI code but resets anyway)
            line = line[:truncate_at + (len(line) - len(clean_line))] + "..."
            clean_line = clean_line[:truncate_at] + "..."

        padding = max(0, width - len(clean_line) - 4)
        print(colorize(vertical, Colors.BOLD) + f"  {line}" + ' ' * padding + colorize(vertical, Colors.BOLD))

    print(colorize(vertical, Colors.BOLD) + ' ' * (width - 2) + colorize(vertical, Colors.BOLD))

    # Bottom border
    bottom_line = bottom_left + horizontal * (width - 2) + bottom_right
    print(colorize(bottom_line, Colors.BOLD))
