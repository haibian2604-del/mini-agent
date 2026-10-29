"""Grader: apply the agent's patch on a clean checkout, run FAIL_TO_PASS, verdict.

Usage:
    uv run python evals/grade_one.py evals/tasks/<task>.json [--keep-workspace]

Requires evals/out/<id>.patch from a prior run_one.py execution.
All git/test operations run inside the container (same sandbox as the agent saw).
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from mini_agent.environments.docker import DockerEnvironment

from run_one import REPOS, WORK, make_work_copy, prepare_repo

EVALS = Path(__file__).resolve().parent
OUT = EVALS / "out"

TEST_TIMEOUT = 600  # sympy import alone is slow; grading is not a sprint


def test_files_from_patch(test_patch: str) -> list[str]:
    """Paths touched by the golden test patch, from its +++ b/ headers."""
    seen: list[str] = []
    for m in re.findall(r"^\+\+\+ b/(.+)$", test_patch, re.M):
        if m not in seen:
            seen.append(m)
    return seen


def pytest_cmd(files: list[str], test_names: list[str]) -> str:
    k_expr = " or ".join(test_names)
    return f"python -m pytest {' '.join(files)} -k \"{k_expr}\""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task_file")
    ap.add_argument("--keep-workspace", action="store_true")
    args = ap.parse_args()

    task = json.loads(Path(args.task_file).read_text())
    task_id = task["instance_id"]
    base = task["base_commit"]
    # dirty-data trap: FAIL_TO_PASS is a JSON-encoded STRING, not a list
    names = task["FAIL_TO_PASS"]
    if isinstance(names, str):
        names = json.loads(names)

    patch_file = OUT / f"{task_id}.patch"
    if not patch_file.exists():
        print(f"no patch found: {patch_file} — run run_one.py first")
        return 2
    agent_patch = patch_file.read_text()

    test_files = test_files_from_patch(task["test_patch"])
    if not test_files:
        print("could not parse any test file path from test_patch")
        return 2
    cmd = pytest_cmd(test_files, names)
    print(f"[grade] test command: {cmd}")
    verdict_notes = []

    work = WORK / f"{task_id}-grade"
    prepare_repo(REPOS / "sympy", task["repo"])
    make_work_copy(REPOS / "sympy", work, base)

    env = DockerEnvironment(image="mini-agent-eval", workspace=work)
    try:
        # ① golden patch on the clean site
        (work / ".test.patch").write_text(task["test_patch"])
        golden = env.execute("git apply .test.patch")
        if golden["returncode"] != 0:
            print(f"[grade] golden test patch failed to apply: {golden['output'][-300:]}")
            return 2

        # ② honesty: with the golden tests but no fix, the new assertions MUST fail
        honest = env.execute(cmd, timeout=TEST_TIMEOUT)
        honest_ok = "OK" if honest["returncode"] != 0 else "UNEXPECTED-PASS"
        print(f"[grade] honesty check (golden only, no fix): rc={honest['returncode']} -> {honest_ok}")

        # ③ undo golden, back to clean
        env.execute(f"git checkout {base} -- {' '.join(test_files)}")

        # ④ agent patch
        if agent_patch.strip():
            (work / ".agent.patch").write_text(agent_patch)
            applied = env.execute("git apply .agent.patch && rm .agent.patch")
            if applied["returncode"] != 0:
                verdict_notes.append(f"agent patch did not apply: {applied['output'][-300:]}")
        else:
            verdict_notes.append("agent produced an empty patch (no changes)")

        # ⑤ undo whatever the agent did to test files — golden must land on base tests
        env.execute(f"git checkout {base} -- {' '.join(test_files)}")

        # ⑥ golden again
        env.execute("git apply .test.patch")

        # ⑦ graded run
        graded = env.execute(cmd, timeout=TEST_TIMEOUT)
        if graded["returncode"] == 5:
            verdict_notes.append("pytest matched no tests (rc=5)")
        resolved = graded["returncode"] == 0
        verdict = "RESOLVED" if resolved and honest_ok == "OK" else "FAILED"

        meta = {
            "instance_id": task_id,
            "verdict": verdict,
            "honesty_check": honest_ok,
            "graded_rc": graded["returncode"],
            "notes": verdict_notes,
        }
        (OUT / f"{task_id}.grade.json").write_text(json.dumps(meta, indent=2))
        print(json.dumps(meta, indent=2))
        return 0 if verdict == "RESOLVED" else 1
    finally:
        env.close()
        if not args.keep_workspace:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
