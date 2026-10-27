"""Tests for DockerEnvironment. Real-container test skips when docker is unavailable."""

import shutil
import subprocess
from pathlib import Path

import pytest

from mini_agent.environments.docker import DockerEnvironment


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


_real_docker = pytest.mark.skipif(not _docker_available(), reason="docker daemon not available")


def _bare_env() -> DockerEnvironment:
    """Instance without __init__ — no container needed for execute()-level tests."""
    env = object.__new__(DockerEnvironment)
    env.container = "test-sandbox"
    env.workspace = Path("/tmp/never-used")
    return env


def _fake_run(returncode: int, stderr: str = "", stdout: str = ""):
    def fake(cmd, **kw):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    return fake


def test_dead_sandbox_is_reported_distinctly(monkeypatch):
    # container stopped externally -> NOT a command failure, must not look like one
    monkeypatch.setattr(
        "mini_agent.environments.docker.subprocess.run",
        _fake_run(127, stderr="Error response from daemon: Container test-sandbox is not running"),
    )
    r = _bare_env().execute("ls")
    assert r["returncode"] == -2
    assert "sandbox unavailable" in r["output"]


def test_daemon_down_is_reported_distinctly(monkeypatch):
    monkeypatch.setattr(
        "mini_agent.environments.docker.subprocess.run",
        _fake_run(1, stderr="Cannot connect to the Docker daemon at unix:///var/run/docker.sock"),
    )
    r = _bare_env().execute("ls")
    assert r["returncode"] == -2
    assert "sandbox unavailable" in r["output"]


def test_normal_command_behavior_unchanged(monkeypatch):
    # healthy container: rc 0 and real command rc both pass through untouched
    monkeypatch.setattr(
        "mini_agent.environments.docker.subprocess.run",
        _fake_run(0, stdout="hello\n"),
    )
    r = _bare_env().execute("echo hello")
    assert r == {"output": "hello\n", "returncode": 0}

    monkeypatch.setattr(
        "mini_agent.environments.docker.subprocess.run",
        _fake_run(3),
    )
    r = _bare_env().execute("exit 3")
    assert r == {"output": "", "returncode": 3}


@_real_docker
def test_docker_environment():
    env = DockerEnvironment()
    try:
        # echo + workdir
        r = env.execute("echo hello && pwd")
        assert "hello" in r["output"] and "/workspace" in r["output"]
        assert r["returncode"] == 0

        # non-zero exit passes through
        r = env.execute("exit 3")
        assert r["returncode"] == 3

        # in-container timeout -> contract's -1
        r = env.execute("sleep 10", timeout=2)
        assert r["returncode"] == -1
        assert "timed out" in r["output"]

        # workspace file survives into the host mount
        r = env.execute("echo data > note.txt")
        assert r["returncode"] == 0
        assert (env.workspace / "note.txt").read_text().strip() == "data"
    finally:
        env.close()  # no zombie containers, even on failure
