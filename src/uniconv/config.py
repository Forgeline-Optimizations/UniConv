"""App configuration: defaults live in code, the user's config.json holds overrides only."""

import json
import logging
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

log = logging.getLogger(__name__)


class PathsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    work_dir: Path | None = None
    output_dir: Path | None = None
    output_mode: Literal["fixed", "beside_source"] = "fixed"


class BehaviorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overwrite: Literal["rename", "overwrite", "skip"] = "rename"
    cleanup_work_dir_on_start: bool = True
    open_folder_after_convert: bool = False


class LimitsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timeout_seconds: int = Field(900, ge=10)
    max_input_mb: int = Field(4096, ge=1)


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    paths: PathsConfig = PathsConfig()
    behavior: BehaviorConfig = BehaviorConfig()
    limits: LimitsConfig = LimitsConfig()
    # Per family; validated against that converter's Options by the registry.
    defaults: dict[str, dict[str, Any]] = {}


def deep_merge(base: dict, changes: dict) -> dict:
    out = dict(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(config_file: Path) -> AppConfig:
    """Code defaults + the user's overrides. Never raises on bad user input."""
    if config_file.exists():
        try:
            return AppConfig.model_validate_json(config_file.read_text(encoding="utf-8"))
        except (ValidationError, UnicodeDecodeError) as exc:
            # pydantic also wraps JSON syntax errors in ValidationError
            log.warning("Invalid config %s, using defaults: %s", config_file, exc)
            try:
                config_file.replace(config_file.with_name("config.invalid.json"))
            except OSError:
                log.warning("Could not move invalid config aside", exc_info=True)
        except OSError:
            log.warning("Could not read config %s, using defaults", config_file, exc_info=True)
    return AppConfig()


def save_user_overrides(config_file: Path, changes: dict) -> AppConfig:
    """Merge `changes` into the user file, validate, then write atomically."""
    current = json.loads(config_file.read_text(encoding="utf-8")) if config_file.exists() else {}
    merged = deep_merge(current, changes)
    cfg = AppConfig.model_validate(merged)  # raise before anything is written
    config_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = config_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(merged, indent=2, default=str), encoding="utf-8")
    tmp.replace(config_file)
    return cfg


def write_reference_copy(config_dir: Path, family_defaults: dict[str, dict]) -> None:
    """Write config.defaults.json: every key with its default, so users know what to override."""
    ref = AppConfig().model_dump(mode="json") | {"defaults": family_defaults}
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.defaults.json").write_text(json.dumps(ref, indent=2), encoding="utf-8")
