"""Tests for mini_agent.agents.default — offline via fake model (monkeypatch)."""

import json

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


def test_run_saves_trajectory(monkeypatch, tmp_path):
    replies = iter([
        ("THOUGHT: 故意格式错误，没有bash块", _U0),
        ("THOUGHT: 先看看\n```bash\necho hello\n```", _U0),
        ("THOUGHT: 完事了\n```bash\necho COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n```", _U0),
    ])
    monkeypatch.setattr(litellm_model, "chat", lambda messages: next(replies))

    out = tmp_path / "traj.json"
    result = run("测试任务", output_path=out)

    data = json.loads(out.read_text())  # valid JSON, Chinese kept readable
    assert data["task"] == "测试任务"
    assert data["exit_status"] == "success"
    assert data["info"]["steps"] == 3
    assert len(data["messages"]) == len(result["messages"])


def test_run_writes_each_round(monkeypatch, tmp_path):
    # 2nd step succeeds; file must already exist and be valid after the run
    replies = iter([
        ("THOUGHT: 先格式错误一轮", _U0),
        ("THOUGHT: 完事了\n```bash\necho COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n```", _U0),
    ])
    monkeypatch.setattr(litellm_model, "chat", lambda messages: next(replies))

    out = tmp_path / "traj.json"
    run("测试任务", output_path=out)

    data = json.loads(out.read_text())
    assert data["exit_status"] == "success"
    # format-error round landed in the saved history too
    assert any("Format error" in m["content"] for m in data["messages"] if m["role"] == "user")


def test_run_uses_injected_env(monkeypatch):
    class FakeEnv:
        def __init__(self):
            self.commands = []

        def execute(self, command, timeout=30):
            self.commands.append(command)
            output = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n" if "COMPLETE" in command else "hi\n"
            return {"output": output, "returncode": 0}

    replies = iter([
        ("THOUGHT: 干活\n```bash\necho hi\n```", _U0),
        ("THOUGHT: 完事了\n```bash\necho COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n```", _U0),
    ])
    monkeypatch.setattr(litellm_model, "chat", lambda messages: next(replies))

    env = FakeEnv()
    result = run("测试", env=env)

    assert env.commands == ["echo hi", "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"]
    assert result["exit_status"] == "success"


def test_run_model_error(monkeypatch):
    # fake raises past chat() entirely -> bypasses retry; verifies agent routing only
    calls = iter([ConnectionError("boom")] * 10)

    def fake_chat(messages):
        raise next(calls)

    monkeypatch.setattr(litellm_model, "chat", fake_chat)
    result = run("测试任务", max_steps=5)
    assert result["exit_status"] == "model_error"
    assert result["messages"][-1]["role"] == "exit"
    assert "model call failed" in result["messages"][-1]["content"]
