"""All path logic. The install dir is usually read-only, so everything writable is per-user."""

import sys
from pathlib import Path

import platformdirs

from uniconv import APP_NAME
from uniconv.config import AppConfig


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def install_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]  # repo root in development


def config_dir() -> Path:
    # Windows: %LOCALAPPDATA%\UniConv  ·  macOS: ~/Library/Application Support/UniConv
    return Path(platformdirs.user_config_dir(APP_NAME, appauthor=False))


def config_file() -> Path:
    return config_dir() / "config.json"


def log_dir() -> Path:
    return Path(platformdirs.user_log_dir(APP_NAME, appauthor=False))


def resolve_work_dir(cfg: AppConfig) -> Path:
    cache = Path(platformdirs.user_cache_dir(APP_NAME, appauthor=False))
    return cfg.paths.work_dir or cache / "work"


def default_output_dir(cfg: AppConfig) -> Path:
    return cfg.paths.output_dir or Path(platformdirs.user_downloads_dir()) / "Converted"


def output_dir_for(cfg: AppConfig) -> Path | None:
    """What a caller puts in Job.output_dir; None means next to each input (review #3)."""
    return None if cfg.paths.output_mode == "beside_source" else default_output_dir(cfg)
