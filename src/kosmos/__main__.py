"""CLI entry point for Kosmos."""

import argparse
from pathlib import Path

from .config import Settings


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="kosmos",
        description="Terminal-based Kanban TUI for markdown task management",
    )
    parser.add_argument(
        "--task-root",
        type=Path,
        default=None,
        help="Path to tasks directory (default: .tasks/)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Build settings from CLI args
    settings_kwargs: dict = {}
    if args.task_root:
        settings_kwargs["task_root"] = args.task_root

    settings = Settings(**settings_kwargs)

    # Import here to avoid circular imports
    from .app import run

    run(settings)


if __name__ == "__main__":
    main()
