"""Typed config: defaults from the pydantic model, overrides from YAML."""

from pathlib import Path

import yaml
from pydantic import BaseModel


class Config(BaseModel):
    model: str
    env: str = "local"  # local | docker
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
