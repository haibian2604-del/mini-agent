"""Tests for mini_agent.environments.local — real subprocess, no mocks needed."""

from mini_agent.environments.local import execute


def test_echo_hello():
    r = execute("echo hello")
    assert "hello" in r["output"]
    assert r["returncode"] == 0


def test_nonzero_exit_returns_normally():
    r = execute("exit 3")
    assert r["returncode"] == 3


def test_timeout_returns_minus_one():
    r = execute("sleep 10", timeout=1)
    assert r["returncode"] == -1
    assert "timed out" in r["output"]


def test_stderr_merged_into_output():
    r = execute("echo oops >&2")
    assert "oops" in r["output"]
