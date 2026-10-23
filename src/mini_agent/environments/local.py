"""Machine-facing side: run shell commands. Knows nothing about the LLM."""

import subprocess


def execute(command: str, timeout: int = 30) -> dict:
    """Run command in a shell; return {"output": str, "returncode": int}.

    stderr is merged into stdout so the model sees errors like in a terminal.
    Timeouts never raise; the agent loop must survive a stuck command.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            stderr=subprocess.STDOUT,
        )
        return {"output": result.stdout, "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"output": f"Command timed out after {timeout}s", "returncode": -1}


if __name__ == "__main__":
    # 1. normal command
    r = execute("echo hello")
    assert "hello" in r["output"] and r["returncode"] == 0, r

    # 2. non-zero exit returns normally, no exception
    r = execute("exit 3")
    assert r["returncode"] == 3, r

    # 3. timeout -> -1, no crash
    r = execute("sleep 10", timeout=1)
    assert r["returncode"] == -1 and "timed out" in r["output"], r

    print("✅ local environment self-test passed")
