"""Tests for mini_agent.models.litellm_model — all offline (fake completion)."""

import pytest

import mini_agent.models.litellm_model as litellm_model
from mini_agent.exceptions import FormatError
from mini_agent.models.litellm_model import chat, parse_action


def test_parse_action_single_block():
    cmd = parse_action("THOUGHT: look around first.\n\n```bash\nls -la src/\n```\n")
    assert cmd == "ls -la src/"


def test_parse_action_two_blocks_raises():
    with pytest.raises(FormatError) as e:
        parse_action("```bash\nls\n```\nthen\n```bash\npwd\n```")
    assert "found 2" in e.value.messages[0]["content"]


def test_parse_action_zero_blocks_raises():
    with pytest.raises(FormatError) as e:
        parse_action("THOUGHT only, no command")
    assert "found 0" in e.value.messages[0]["content"]


class _FakeMsg:
    content = "hi"


class _FakeChoice:
    message = _FakeMsg()


class _FakeUsage:
    prompt_tokens = 10
    completion_tokens = 5


class _FakeResp:
    choices = [_FakeChoice()]
    usage = _FakeUsage()


def test_chat_returns_content_and_usage(monkeypatch):
    monkeypatch.setattr(litellm_model, "completion", lambda **kw: _FakeResp())
    content, usage = chat([{"role": "user", "content": "ping"}])
    assert content == "hi"
    assert usage == {"prompt_tokens": 10, "completion_tokens": 5, "cost_usd": 0.0}


def test_chat_none_content_becomes_empty_string(monkeypatch):
    monkeypatch.setattr(litellm_model, "completion", lambda **kw: _FakeResp())

    class _NoneMsg:
        content = None

    class _NoneChoice:
        message = _NoneMsg()

    class _NoneResp:
        choices = [_NoneChoice()]
        usage = _FakeUsage()

    monkeypatch.setattr(litellm_model, "completion", lambda **kw: _NoneResp())
    content, _ = chat([])
    assert content == ""


def test_chat_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def flaky(**kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("network blip")
        return _FakeResp()

    monkeypatch.setattr(litellm_model, "completion", flaky)
    monkeypatch.setattr(litellm_model.time, "sleep", lambda s: None)
    content, usage = chat([])
    assert calls["n"] == 3
    assert content == "hi"


def test_chat_auth_error_no_retry(monkeypatch):
    calls = {"n": 0}

    def bad_key(**kw):
        calls["n"] += 1
        raise litellm_model.AuthenticationError("bad key", "openai", "glm-5.3-flash")

    monkeypatch.setattr(litellm_model, "completion", bad_key)
    monkeypatch.setattr(litellm_model.time, "sleep", lambda s: None)
    with pytest.raises(litellm_model.AuthenticationError):
        chat([])
    assert calls["n"] == 1  # never retried
