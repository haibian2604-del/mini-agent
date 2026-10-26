"""Typed config: defaults from the pydantic model, overrides from YAML."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict


class Config(BaseModel):
    # extra="forbid": a typo'd yaml key (max_step) explodes instead of silently using the default
    model_config = ConfigDict(extra="forbid")

    model: str
    env: Literal["local", "docker"] = "local"
    max_steps: int = 20
    max_cost_usd: float = 5.0
    max_total_tokens: int = 150_000
    max_consecutive_format_errors: int = 3


def load_config(path: Path | str | None = None) -> Config:
    """Load YAML config; missing keys fall back to model defaults.

    None -> the packaged config/default.yaml.
    """
    if path is None:
        path = Path(__file__).parent / "default.yaml"
    data = yaml.safe_load(Path(path).read_text()) or {}
    return Config(**data)
