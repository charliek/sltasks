"""CLI entry point for sltasks."""

import argparse
from pathlib import Path

from .config import Settings
from .logging import setup_logging


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
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (-v for INFO, -vv for DEBUG)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Path to write logs to file",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )
    parser.add_argument(
        "--github-setup",
        nargs="?",
        const=True,
        default=None,
        metavar="PROJECT_URL",
        help="Interactive setup for GitHub Projects integration. Optionally pass project URL.",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Build settings from CLI args
    settings_kwargs: dict = {}
    if args.task_root:
        settings_kwargs["project_root"] = args.task_root
    if args.verbose:
        settings_kwargs["verbose"] = args.verbose
    if args.log_file:
        settings_kwargs["log_file"] = args.log_file

    settings = Settings(**settings_kwargs)

    # Setup logging based on verbosity
    setup_logging(settings.verbose, settings.log_file)

    # Handle --generate command
    if args.generate:
        from .cli.generate import run_generate

        exit_code = run_generate(settings.project_root)
        raise SystemExit(exit_code)

    # Handle --github-setup command
    if args.github_setup is not None:
        from .cli.github_setup import run_github_setup

        # args.github_setup is True if flag only, or string if URL provided
        project_url = args.github_setup if isinstance(args.github_setup, str) else None
        exit_code = run_github_setup(settings.project_root, project_url)
        raise SystemExit(exit_code)

    # Import here to avoid circular imports
    from .app import run

    run(settings)


if __name__ == "__main__":
    main()
