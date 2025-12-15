"""Application settings."""

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    project_root: Path = Field(
        default=Path(),
        description="Path to project root containing sltasks.yml",
    )

    editor: str = Field(
        default_factory=lambda: os.environ.get("EDITOR", "vim"),
        description="Editor for task editing",
    )

    verbose: int = Field(
        default=0,
        description="Verbosity level (0=off, 1=INFO, 2+=DEBUG)",
    )

    log_file: Path | None = Field(
        default=None,
        description="Optional path to write logs to file",
    )

    model_config = {
        "env_prefix": "KOSMOS_",
    }
