"""Application settings."""

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    task_root: Path = Field(
        default=Path(".tasks"),
        description="Path to tasks directory",
    )

    editor: str = Field(
        default_factory=lambda: os.environ.get("EDITOR", "vim"),
        description="Editor for task editing",
    )

    model_config = {
        "env_prefix": "KOSMOS_",
    }
