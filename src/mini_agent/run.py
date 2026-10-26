"""Entry point: uv run python -m mini_agent.run "task text" [--env ...] [--model ...]

Priority: CLI flags > config/default.yaml > built-in defaults.
Secrets (API_KEY/BASE_URL) stay in .env; behavior config lives in yaml.
"""

import argparse
from datetime import datetime
from pathlib import Path

from mini_agent.agents import default
from mini_agent.config import load_config
from mini_agent.environments import local
from mini_agent.environments.docker import DockerEnvironment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task", nargs="?", default=None)          # 不传就 input()
    parser.add_argument("--env", choices=["local", "docker"], default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--config", default=None, help="path to yaml config")
    args = parser.parse_args()

    cfg = load_config(args.config)
    model = args.model or cfg.model
    env_name = args.env or cfg.env

    task = args.task or input("任务: ")
    env = DockerEnvironment() if env_name == "docker" else local
    out = Path("trajectories") / f"{datetime.now():%Y%m%d-%H%M%S}.json"

    try:
        result = default.run(
            task,
            model=model,
            env=env,
            output_path=out,
            max_steps=cfg.max_steps,
            max_cost_usd=cfg.max_cost_usd,
            max_total_tokens=cfg.max_total_tokens,
            max_consecutive_format_errors=cfg.max_consecutive_format_errors,
        )
    finally:
        if hasattr(env, "close"):  # duck typing: local module has no close
            env.close()

    print(f"\n== {result['exit_status']} ==")
    print(f"trajectory: {out}")


if __name__ == "__main__":
    main()
