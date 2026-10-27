"""Docker-backed environment: same .execute() contract as local, with a lifecycle."""

import shlex
import subprocess
from pathlib import Path

# docker CLI signatures that mean "the sandbox is gone" (not the command's fault)
_DEAD_SANDBOX_MARKERS = (
    "is not running",
    "No such container",
    "Cannot connect to the Docker daemon",
)


class DockerEnvironment:
    """Sandboxed shell inside a container.

    Contract identical to environments.local.execute, so the agent can use
    either without knowing. Lifecycle: __init__ starts, close() destroys.
    """

    def __init__(
        self,
        image: str = "python:3.12-slim",
        container: str = "mini-agent-sandbox",
        workspace: Path | str | None = None,
    ):
        self.container = container
        self.workspace = Path(workspace) if workspace else Path("workspace")
        self.workspace = self.workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

        # a container left over from a crashed run blocks --name; rm is best-effort
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)
        subprocess.run(
            [
                "docker", "run", "-d", "--name", container,
                "-v", f"{self.workspace}:/workspace",
                "-w", "/workspace",
                image, "sleep", "infinity",
            ],
            check=True,
            capture_output=True,
        )

    def execute(self, command: str, timeout: int = 30) -> dict:
        # timeout runs INSIDE the container: killing the outer docker client
        # (subprocess timeout) would leave the real command orphaned in there.
        # 2>&1 merges stderr so the model can see errors and self-repair.
        inner = f"timeout {timeout}s bash -c {shlex.quote(command)} 2>&1"
        try:
            result = subprocess.run(
                ["docker", "exec", self.container, "bash", "-c", inner],
                capture_output=True,
                text=True,
                timeout=timeout + 10,  # outer net for a wedged docker client
            )
        except subprocess.TimeoutExpired:
            return {"output": f"Command timed out after {timeout}s", "returncode": -1}

        if result.returncode != 0 and any(
            marker in (result.stderr or "") + (result.stdout or "")
            for marker in _DEAD_SANDBOX_MARKERS
        ):
            # sandbox died externally (docker stop / crash / daemon down): without
            # this, the model sees docker's raw error and blames its own command
            return {
                "output": (
                    "[sandbox unavailable] The container backing this environment is not "
                    "running (stopped externally or crashed). NO command can succeed — do not "
                    "retry or rewrite your command; the task cannot continue. "
                    f"docker error: {result.stderr or result.stdout}"
                ),
                "returncode": -2,
            }

        if result.returncode == 124:  # coreutils timeout's exit code
            # ponytail: a command that genuinely exits 124 is misreported as a timeout
            return {"output": result.stdout + f"\n[timed out after {timeout}s]", "returncode": -1}
        return {"output": result.stdout, "returncode": result.returncode}

    def close(self):
        subprocess.run(["docker", "rm", "-f", self.container], capture_output=True)
