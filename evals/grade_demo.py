"""Manual grading demo for sympy__sympy-24909 — v2, fixed probe bugs.

Lessons baked in:
- pytest rc must come from pytest, not a `| tail` pipeline (bash pipe eats it)
- order: apply agent patch FIRST, THEN reset test files, THEN golden test patch
  (the agent patch may also touch test files and would conflict otherwise)
"""
import json
import shutil
import subprocess
from pathlib import Path

from mini_agent.environments.docker import DockerEnvironment

TASK = json.load(open("evals/tasks/sympy__sympy-24909.json"))
WORK = Path("evals/work/grade-demo")
TEST_FILE = "sympy/physics/units/tests/test_prefixes.py"


def prep_clean_copy() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.copytree("evals/repos/sympy", WORK, symlinks=True)
    subprocess.run(["git", "checkout", TASK["base_commit"]], cwd=WORK, capture_output=True)


prep_clean_copy()
env = DockerEnvironment(image="mini-agent-eval", container="grade-demo", workspace=WORK)


def apply(text: str, what: str) -> bool:
    r = env.execute(f"git apply - <<'PATCHEOF'\n{text}\nPATCHEOF")
    print(f"$ apply {what}: rc={r['returncode']}")
    return r["returncode"] == 0


def pytest_rc() -> tuple[int, str]:
    # NO pipe: the contract's returncode must be pytest's own
    r = env.execute(f"python -m pytest {TEST_FILE} -k test_prefix_operations -q")
    return r["returncode"], r["output"][-250:]


try:
    run_mpmath = env.execute("pip install -q mpmath")
    assert run_mpmath["returncode"] == 0, run_mpmath["output"]

    # -- honesty check: golden tests alone must FAIL on the pristine base
    assert apply(TASK["test_patch"], "golden test patch (pristine)")
    rc, out = pytest_rc()
    print(f"   pristine rc={rc} (expect != 0)")
    print("   诚实检查:", "FAIL ✅ 判卷有效" if rc != 0 else "PASS ❌ 黄金测试没牙!")
    env.execute(f"git checkout HEAD -- {TEST_FILE}")  # undo

    # -- real grading: agent patch -> reset test files -> golden tests
    assert apply(Path("evals/out/sympy__sympy-24909.patch").read_text(), "agent patch")
    env.execute(f"git checkout HEAD -- {TEST_FILE}")
    assert apply(TASK["test_patch"], "golden test patch")

    rc, out = pytest_rc()
    print(f"   graded rc={rc}  tail:\n{out}")
    print()
    print("=== 最终裁决 ===", "RESOLVED ✅" if rc == 0 else "FAILED ❌")
finally:
    env.close()
    shutil.rmtree(WORK, ignore_errors=True)
