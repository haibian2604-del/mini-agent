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


def test_parse_action_accepts_unlabeled_block():
    # issue 005: models often drop the language label
    cmd = parse_action("THOUGHT: look around.\n\n```\necho hello\n```\n")
    assert cmd == "echo hello"


def test_parse_action_rejects_python_only_block():
    # strategy: non-bash labels are not actions (can't run in a bash shell)
    with pytest.raises(FormatError) as e:
        parse_action("THOUGHT: calc\n\n```python\nprint(1)\n```\n")
    assert "found 0" in e.value.messages[0]["content"]


def test_parse_action_mixed_blocks_no_false_positive():
    # python snippet in THOUGHT + one bash command -> bash wins, python ignored
    text = (
        "THOUGHT: here is some python\n\n```python\nprint(1)\n```\n"
        "and the action:\n\n```bash\necho hello\n```\n"
    )
    assert parse_action(text) == "echo hello"


def test_parse_action_unlabeled_plus_bash_counts_both():
    # both are actionable candidates -> exactly-one constraint still applies
    text = "```\necho a\n```\n```bash\necho b\n```"
    with pytest.raises(FormatError) as e:
        parse_action(text)
    assert "found 2" in e.value.messages[0]["content"]


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
    content, usage = chat([{"role": "user", "content": "ping"}], model="m")
    assert content == "hi"
    assert usage == {"prompt_tokens": 10, "completion_tokens": 5, "cost_usd": 0.0}


def test_chat_none_content_becomes_empty_string(monkeypatch):
    class _NoneMsg:
        content = None

    class _NoneChoice:
        message = _NoneMsg()

    class _NoneResp:
        choices = [_NoneChoice()]
        usage = _FakeUsage()

    monkeypatch.setattr(litellm_model, "completion", lambda **kw: _NoneResp())
    content, _ = chat([], model="m")
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
    content, usage = chat([], model="m")
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
        chat([], model="m")
    assert calls["n"] == 1  # never retried


def test_chat_passes_model_to_completion(monkeypatch):
    seen = {}

    def spy(**kw):
        seen.update(kw)
        return _FakeResp()

    monkeypatch.setattr(litellm_model, "completion", spy)
    chat([], model="openai/glm-x")
    assert seen["model"] == "openai/glm-x"  # explicit injection, no os.environ read
