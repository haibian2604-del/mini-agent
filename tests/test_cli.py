"""Tests for the CLI (typer CliRunner). No API calls here."""

import json
import os

import pytest
from typer.testing import CliRunner

from mini_agent.run import app

runner = CliRunner()

_TRAJECTORY = {
    "task": "测试任务",
    "exit_status": "success",
    "info": {"steps": 2, "total_cost_usd": 0.0, "total_tokens": 500},
    "messages": [
        {"role": "system", "content": "SYSTEM PROMPT TEXT"},
        {"role": "user", "content": "测试任务"},
        {"role": "assistant", "content": "THOUGHT: 先看看\n\n```bash\necho hello\n```"},
        {"role": "user", "content": "<returncode>0</returncode>\n<output>\nhello\n</output>"},
        {"role": "assistant", "content": "THOUGHT: 完事\n\n```bash\necho COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n```"},
        {"role": "user", "content": "<returncode>0</returncode>\n<output>\nCOMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n</output>"},
        {"role": "exit", "content": "Task completed successfully after 2 steps."},
    ],
}


def test_inspect_renders_trajectory(tmp_path):
    p = tmp_path / "traj.json"
    p.write_text(json.dumps(_TRAJECTORY, ensure_ascii=False))

    result = runner.invoke(app, ["inspect", str(p)])

    assert result.exit_code == 0
    out = result.output
    assert "测试任务" in out
    assert "success" in out
    assert "echo hello" in out          # bash block rendered
    assert "system prompt, 18 chars" in out  # folded
    assert "Task completed successfully" in out  # exit message


def test_inspect_failure_shows_red_status(tmp_path):
    traj = dict(_TRAJECTORY, exit_status="limits_exceeded")
    p = tmp_path / "traj.json"
    p.write_text(json.dumps(traj, ensure_ascii=False))

    result = runner.invoke(app, ["inspect", str(p)])
    assert result.exit_code == 0
    assert "limits_exceeded" in result.output


def test_run_interactive_exit_immediately():
    # empty interactive loop: input "exit" quits before any API call
    result = runner.invoke(app, ["run"], input="exit\n")
    assert result.exit_code == 0


def test_inspect_last_opens_newest(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "trajectories").mkdir()
    old = tmp_path / "trajectories" / "20260101-000000.json"
    new = tmp_path / "trajectories" / "20260102-000000.json"
    old.write_text(json.dumps(dict(_TRAJECTORY, task="OLD"), ensure_ascii=False))
    new.write_text(json.dumps(dict(_TRAJECTORY, task="NEW"), ensure_ascii=False))
    os.utime(old, (1, 1))  # force mtime order, independent of creation order

    result = runner.invoke(app, ["inspect", "--last"])

    assert result.exit_code == 0
    assert "NEW" in result.output
    assert "OLD" not in result.output


def test_inspect_last_empty_dir(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "trajectories").mkdir()

    result = runner.invoke(app, ["inspect", "--last"])

    assert result.exit_code != 0
    assert "No trajectories" in result.output
