"""Single-task eval runner: repo prep -> sandbox -> agent -> patch.

Usage:
    uv run python evals/run_one.py evals/tasks/<task>.json [--dry-run] [--keep-workspace]

--dry-run executes only the pipeline (clone/checkout/mount/container + empty
diff check) and never calls the API — validate the plumbing before burning tokens.
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from mini_agent.agents import default
from mini_agent.config import load_config
from mini_agent.environments.docker import DockerEnvironment

EVALS = Path(__file__).resolve().parent
REPOS = EVALS / "repos"
WORK = EVALS / "work"
OUT = EVALS / "out"

TASK_TEMPLATE = """You are working in the sympy repository, checked out at /workspace (your cwd).
An issue has been filed against this code:

{problem_statement}

Locate the root cause, fix it in the source, and verify by running the relevant
tests with `python -m pytest <test file you identified>`. Finish as usual.
"""


def prepare_repo(cache: Path, repo_slug: str) -> None:
    if cache.exists():
        print(f"[repo] cache hit: {cache}")
        return
    # github direct first; gitee mirror as fallback. HTTP/1.1: github's HTTP/2
    # framing breaks on flaky networks.
    slug = repo_slug.split("/")[-1]
    candidates = [
        f"https://github.com/{repo_slug}.git",
        f"https://gitee.com/mirrors/{slug}.git",
    ]
    last_err = None
    for url in candidates:
        print(f"[repo] cloning {url} -> {cache} (one-time, partial: blobs on demand)...")
        t0 = time.time()
        proc = subprocess.run(
            ["git", "-c", "http.version=HTTP/1.1", "clone", "--filter=blob:none", url, str(cache)],
            capture_output=True,
        )
        if proc.returncode == 0:
            print(f"[repo] cloned in {time.time() - t0:.0f}s")
            return
        last_err = proc.stderr.decode(errors="replace")[-300:]
        print(f"[repo] clone failed: {last_err}")
        shutil.rmtree(cache, ignore_errors=True)
    raise RuntimeError(f"all clone candidates failed, last error: {last_err}")


def make_work_copy(cache: Path, work_dir: Path, base_commit: str) -> None:
    if work_dir.exists():
        shutil.rmtree(work_dir)
    shutil.copytree(cache, work_dir, symlinks=True)
    proc = subprocess.run(
        ["git", "checkout", base_commit],
        cwd=work_dir,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"checkout {base_commit} failed: {proc.stderr.decode(errors='replace')[-300:]}"
        )
    print(f"[work] {work_dir} @ {base_commit[:8]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task_file")
    ap.add_argument("--dry-run", action="store_true", help="pipeline only, no API calls")
    ap.add_argument("--keep-workspace", action="store_true", help="keep work copy for debugging")
    args = ap.parse_args()

    task = json.loads(Path(args.task_file).read_text())
    task_id = task["instance_id"]
    work_dir = WORK / task_id
    OUT.mkdir(parents=True, exist_ok=True)

    prepare_repo(REPOS / "sympy", task["repo"])
    make_work_copy(REPOS / "sympy", work_dir, task["base_commit"])

    cfg = load_config()
    environment = DockerEnvironment(image="mini-agent-eval", workspace=work_dir)
    try:
        agent_task = TASK_TEMPLATE.format(problem_statement=task["problem_statement"])
        if args.dry_run:
            # plumbing check: container live + git works + empty diff on fresh checkout
            probe = environment.execute("git add -A && git diff --cached")
            print(f"[dry-run] would run agent with {len(agent_task)} chars task")
            print(f"[dry-run] git diff probe: rc={probe['returncode']} output={probe['output']!r}")
            return 0

        traj_path = OUT / f"{task_id}.traj.json"
        t0 = time.time()
        result = default.run(
            agent_task,
            model=cfg.model,
            env=environment,
            output_path=traj_path,
            max_steps=40,
            max_cost_usd=cfg.max_cost_usd,
            max_total_tokens=cfg.max_total_tokens,
            max_consecutive_format_errors=cfg.max_consecutive_format_errors,
        )
        duration = time.time() - t0

        patch_obs = environment.execute("git add -A && git diff --cached")
        patch = patch_obs["output"]
        (OUT / f"{task_id}.patch").write_text(patch)

        info = json.loads(traj_path.read_text())["info"]
        meta = {
            "instance_id": task_id,
            "exit_status": result["exit_status"],
            "steps": info["steps"],
            "total_tokens": info["total_tokens"],
            "patch_lines": len(patch.splitlines()),
            "duration_s": round(duration, 1),
        }
        (OUT / f"{task_id}.meta.json").write_text(json.dumps(meta, indent=2))
        print(json.dumps(meta, indent=2))
        return 0 if result["exit_status"] == "success" else 1
    finally:
        environment.close()
        if not args.keep_workspace:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
