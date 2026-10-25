"""Tests for DockerEnvironment — skipped when docker is not installed."""

import shutil

import pytest

from mini_agent.environments.docker import DockerEnvironment

pytestmark = pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")


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
