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
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        return {"output": result.stdout, "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"output": f"Command timed out after {timeout}s", "returncode": -1}


