"""CLI entry point for sltasks."""

import argparse
from pathlib import Path

from .config import Settings


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="sltasks",
        description="Terminal-based Kanban TUI for markdown task management",
    )
    parser.add_argument(
        "--task-root",
        type=Path,
        default=None,
        help="Path to project root containing sltasks.yml (default: current directory)",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate default sltasks.yml config in task directory and exit",
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
        settings_kwargs["project_root"] = args.task_root

    settings = Settings(**settings_kwargs)

    # Handle --generate command
    if args.generate:
        from .cli.generate import run_generate

        exit_code = run_generate(settings.project_root)
        raise SystemExit(exit_code)

    # Import here to avoid circular imports
    from .app import run

    run(settings)


if __name__ == "__main__":
    main()
