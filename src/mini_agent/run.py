"""CLI: mini-agent run "task" / mini-agent inspect traj.json

UI concerns (typer/rich) live ONLY here — the agent loop stays plain print.
"""

import json
import re
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.syntax import Syntax

from mini_agent.agents import default
from mini_agent.config import Config, load_config
from mini_agent.environments import local
from mini_agent.environments.docker import DockerEnvironment

app = typer.Typer(help="A minimal coding agent.")
console = Console()

_ACTION_RE = re.compile(r"```bash\s*(.*?)```", re.DOTALL)


def _build_env(name: str):
    return DockerEnvironment() if name == "docker" else local


def _run_one(task: str, cfg: Config, model: str, environment) -> None:
    out = Path("trajectories") / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    result = default.run(
        task,
        model=model,
        env=environment,
        output_path=out,
        max_steps=cfg.max_steps,
        max_cost_usd=cfg.max_cost_usd,
        max_total_tokens=cfg.max_total_tokens,
        max_consecutive_format_errors=cfg.max_consecutive_format_errors,
    )
    console.print(f"\n== {result['exit_status']} ==")
    console.print(f"trajectory: {out}\n")


def _start(
    task: str | None,
    env: str | None,
    model: str | None,
    config: Path | None,
    max_steps: int | None,
) -> None:
    cfg = load_config(config)
    model = model or cfg.model
    environment = _build_env(env or cfg.env)
    limit = max_steps or cfg.max_steps

    try:
        if task:
            _run_one(task, cfg, model, environment)
        else:
            console.print("[bold]交互模式[/]（空行或 exit 退出）")
            while True:
                try:
                    t = input("任务> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not t or t in ("exit", "quit"):
                    break
                _run_one(t, cfg, model, environment)
    finally:
        if hasattr(environment, "close"):  # duck typing: local module has no close
            environment.close()


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context):
    """A minimal coding agent. Run without a subcommand for interactive mode."""
    if ctx.invoked_subcommand is None:
        _start(None, None, None, None, None)
        raise typer.Exit()


@app.command()
def run(
    task: str | None = typer.Argument(None),
    env: str | None = typer.Option(None, "--env", help="local | docker (default: yaml)"),
    model: str | None = typer.Option(None, "--model", help="litellm model name (default: yaml)"),
    config: Path | None = typer.Option(None, "--config", help="path to yaml config"),
    max_steps: int | None = typer.Option(None, "--max-steps"),
):
    """跑一个任务。不带 task 参数 → 进入交互模式。"""
    _start(task, env, model, config, max_steps)


def _print_assistant(content: str) -> None:
    m = _ACTION_RE.search(content)
    if m:
        thought = content[: m.start()].strip()
        if thought:
            console.print(f"[dim]{escape(thought)}[/dim]")
        console.print(Syntax(m.group(1).strip(), "bash", background_color="default"))
    else:
        console.print(f"[dim]{escape(content)}[/dim]")


@app.command()
def inspect(
    path: Path | None = typer.Argument(None),
    last: bool = typer.Option(False, "--last", help="open the newest trajectory"),
):
    """回放一条轨迹。"""
    if path is None:
        if not last:
            console.print("[red]Provide a trajectory path, or use --last.[/red]")
            raise typer.Exit(1)
        candidates = sorted(
            Path("trajectories").glob("*.json"), key=lambda p: p.stat().st_mtime
        )
        if not candidates:
            console.print("[red]No trajectories in trajectories/ — run a task first.[/red]")
            raise typer.Exit(1)
        path = candidates[-1]
    data = json.loads(path.read_text())
    status = data["exit_status"]
    color = "green" if status == "success" else "red"
    info = data.get("info", {})
    console.print(f"[bold]task:[/] {escape(data['task'])}")
    console.print(
        f"[bold]status:[/] [{color}]{status}[/]  "
        f"steps: {info.get('steps', '?')}  "
        f"tokens: {info.get('total_tokens', '?')}  "
        f"cost: ${info.get('total_cost_usd', 0.0)}"
    )
    console.print()
    for m in data["messages"]:
        role, content = m["role"], m["content"]
        if role == "system":
            console.print("[dim]" + escape(f"[system prompt, {len(content)} chars]") + "[/dim]")
        elif role == "assistant":
            console.print("[bold cyan]assistant[/]")
            _print_assistant(content)
        elif role == "exit":
            console.print(f"[bold]exit: {escape(content)}[/]")
        elif "<returncode>" in content:
            console.print("[dim]" + escape(content)[:2000] + "[/]")
        else:
            console.print(f"[yellow]{escape(content)[:2000]}[/]")
        console.print()


if __name__ == "__main__":
    app()
