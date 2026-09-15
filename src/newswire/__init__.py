"""newswire - a config-driven source -> digest -> channel news notifier."""

from newswire.config import Config, ConfigError, load_config
from newswire.core import run

__version__ = "1.0.0"

__all__ = ["Config", "ConfigError", "load_config", "run", "__version__"]
