"""Entry point: uv run python -m mini_agent.run "task text\""""

import sys

from mini_agent.agents import default


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else input("任务: ")
    result = default.run(task)
    print(f"\n== {result['exit_status']} ==")


if __name__ == "__main__":
    main()
