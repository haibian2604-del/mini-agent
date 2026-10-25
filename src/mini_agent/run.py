"""Entry point: uv run python -m mini_agent.run "task text" [--env local|docker]"""

import argparse
from datetime import datetime
from pathlib import Path

from mini_agent.agents import default
from mini_agent.environments import local
from mini_agent.environments.docker import DockerEnvironment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task", nargs="?", default=None)     # 不传就 input()
    parser.add_argument("--env", choices=["local", "docker"], default="local")
    args = parser.parse_args()

    task = args.task or input("任务: ")
    env = DockerEnvironment() if args.env == "docker" else local
    out = Path("trajectories") / f"{datetime.now():%Y%m%d-%H%M%S}.json"

    try:
        result = default.run(task, env=env, output_path=out)
    finally:
        if hasattr(env, "close"):  # duck typing: local module has no close
            env.close()

    print(f"\n== {result['exit_status']} ==")
    print(f"trajectory: {out}")


if __name__ == "__main__":
    main()
