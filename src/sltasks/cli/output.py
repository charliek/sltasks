"""Colorful CLI output helpers."""

import sys

# ANSI color codes
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RED = "\033[31m"
RESET = "\033[0m"
CHECK = "\u2713"  # ✓
BULLET = "\u2022"  # •
CROSS = "\u2717"  # ✗


def _supports_color() -> bool:
    """Check if terminal supports color output."""
    # Check if stdout is a TTY
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    return True


def _colorize(text: str, color: str) -> str:
    """Apply color to text if terminal supports it."""
    if _supports_color():
        return f"{color}{text}{RESET}"
    return text


def success(message: str) -> None:
    """Print success message with green checkmark."""
    check = _colorize(CHECK, GREEN)
    print(f"{check} {message}")


def info(message: str) -> None:
    """Print info message with yellow bullet."""
    bullet = _colorize(BULLET, YELLOW)
    print(f"{bullet} {message}")


def header(message: str) -> None:
    """Print header message in blue."""
    print(_colorize(message, BLUE))


def error(message: str) -> None:
    """Print error message with red cross."""
    cross = _colorize(CROSS, RED)
    print(f"{cross} {message}")
