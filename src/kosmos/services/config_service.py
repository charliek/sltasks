"""Configuration service for loading sltasks.yml."""

import logging
from pathlib import Path

import yaml

from kosmos.models.sltasks_config import BoardConfig, SltasksConfig

logger = logging.getLogger(__name__)


class ConfigService:
    """Service for loading and caching application configuration."""

    CONFIG_FILE = "sltasks.yml"

    def __init__(self, task_root: Path) -> None:
        """Initialize the config service.

        Args:
            task_root: Path to the .tasks directory
        """
        self.task_root = task_root
        self._config: SltasksConfig | None = None
        self._config_error: str | None = None

    @property
    def has_config_error(self) -> bool:
        """Check if there was an error loading config."""
        return self._config_error is not None

    @property
    def config_error(self) -> str | None:
        """Get the config error message if any."""
        return self._config_error

    def get_config(self) -> SltasksConfig:
        """Get configuration, loading from file if not cached."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def get_board_config(self) -> BoardConfig:
        """Convenience method to get board configuration."""
        return self.get_config().board

    def reload(self) -> None:
        """Clear cached configuration, forcing reload on next access."""
        self._config = None
        self._config_error = None

    def _load_config(self) -> SltasksConfig:
        """Load configuration from file or return default."""
        config_path = self.task_root / self.CONFIG_FILE
        self._config_error = None

        if not config_path.exists():
            logger.debug(f"No {self.CONFIG_FILE} found, using defaults")
            return SltasksConfig.default()

        try:
            with open(config_path) as f:
                data = yaml.safe_load(f)

            if data is None:
                self._config_error = f"{self.CONFIG_FILE} is empty"
                logger.warning(self._config_error)
                return SltasksConfig.default()

            config = SltasksConfig(**data)
            logger.info(
                f"Loaded {self.CONFIG_FILE} with {len(config.board.columns)} columns"
            )
            return config

        except yaml.YAMLError as e:
            self._config_error = f"Invalid YAML in {self.CONFIG_FILE}: {e}"
            logger.warning(self._config_error)
            return SltasksConfig.default()

        except Exception as e:
            self._config_error = f"Error loading {self.CONFIG_FILE}: {e}"
            logger.warning(self._config_error)
            return SltasksConfig.default()
