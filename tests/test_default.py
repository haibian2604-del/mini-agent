"""Tests for mini_agent.agents.default — offline via fake model (monkeypatch)."""

import mini_agent.models.litellm_model as litellm_model
from mini_agent.agents.default import run

_U0 = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}


def test_run_success_path(monkeypatch):
    replies = iter([
        ("THOUGHT: 故意格式错误，没有bash块", _U0),                                        # 1: format error
        ("THOUGHT: 先看看\n```bash\necho hello\n```", _U0),                                # 2: real command
        ("THOUGHT: 完事了\n```bash\necho COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n```", _U0),  # 3: done
    ])
    monkeypatch.setattr(litellm_model, "chat", lambda messages: next(replies))

    result = run("测试任务")

    assert result["exit_status"] == "success"
    assert result["messages"][-1]["role"] == "exit"

    user_msgs = [m["content"] for m in result["messages"] if m["role"] == "user"]
    assert "Format error" in user_msgs[1]  # error fed back -> self-correction loop
    assert "hello" in user_msgs[2]         # observation fed back -> execution loop


def test_run_consecutive_format_errors_limit(monkeypatch):
    monkeypatch.setattr(
        litellm_model, "chat", lambda messages: ("THOUGHT: 永远不写bash块", _U0)
    )
    result = run("测试任务", max_consecutive_format_errors=3)
    assert result["exit_status"] == "limits_exceeded"
    assert "consecutive format errors" in result["messages"][-1]["content"]


def test_run_token_limit(monkeypatch):
    # probe result: cost_usd is 0.0 on custom endpoints, so tokens are the real budget
    replies = iter([("whatever", {"prompt_tokens": 80_000, "completion_tokens": 0, "cost_usd": 0.0})] * 5)
    monkeypatch.setattr(litellm_model, "chat", lambda messages: next(replies))

    result = run("测试任务", max_total_tokens=150_000)
    assert result["exit_status"] == "limits_exceeded"
    assert "token limit" in result["messages"][-1]["content"]


def test_run_cost_limit(monkeypatch):
    replies = iter(
        [("whatever", {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 2.0})] * 5
    )
    monkeypatch.setattr(litellm_model, "chat", lambda messages: next(replies))

    result = run("测试任务", max_cost_usd=5.0)
    assert result["exit_status"] == "limits_exceeded"
    assert "cost limit" in result["messages"][-1]["content"]


def test_run_max_steps_limit(monkeypatch):
    monkeypatch.setattr(
        litellm_model,
        "chat",
        lambda messages: ("THOUGHT: 再来一步\n```bash\necho hi\n```", _U0),
    )
    result = run("测试任务", max_steps=5)
    assert result["exit_status"] == "limits_exceeded"
    assert "max steps" in result["messages"][-1]["content"]
