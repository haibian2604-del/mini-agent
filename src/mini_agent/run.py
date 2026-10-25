"""Entry point: uv run python -m mini_agent.run "task text\""""

import sys
from datetime import datetime
from pathlib import Path

from mini_agent.agents import default


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else input("任务: ")
    out = Path("trajectories") / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    result = default.run(task, output_path=out)
    print(f"\n== {result['exit_status']} ==")
    print(f"trajectory: {out}")


if __name__ == "__main__":
    main()
