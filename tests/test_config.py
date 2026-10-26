"""Tests for config loading: yaml overrides pydantic defaults."""

import pytest
from pydantic import ValidationError

from mini_agent.config import load_config


def test_load_config_merges_defaults(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text("model: openai/glm-x\nmax_steps: 3\n")
    cfg = load_config(p)
    assert cfg.model == "openai/glm-x"
    assert cfg.max_steps == 3
    assert cfg.env == "local"  # default
    assert cfg.max_cost_usd == 5.0  # default
    assert cfg.max_total_tokens == 150_000  # default
    assert cfg.max_consecutive_format_errors == 3  # default


def test_load_packaged_default_config():
    cfg = load_config()  # the shipped config/default.yaml
    assert "/" in cfg.model  # provider prefix present (litellm contract)


def test_config_rejects_unknown_keys(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text("model: openai/glm-x\nmax_step: 3\n")  # typo: max_step
    with pytest.raises(ValidationError, match="max_step"):
        load_config(p)


def test_config_rejects_bad_env(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text("model: openai/glm-x\nenv: kubernetes\n")
    with pytest.raises(ValidationError, match="env"):
        load_config(p)
