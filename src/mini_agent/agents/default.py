"""The agent loop: model <-> shell, linear history, append-only.

Control flow = exceptions: every exit reason raises InterruptAgentFlow carrying
the messages to append; the loop's only exit signal is a role="exit" message.
"""

import json
from pathlib import Path

from mini_agent.config.prompts import SYSTEM_PROMPT
from mini_agent.environments import local
from mini_agent.exceptions import (
    FormatError,
    InterruptAgentFlow,
    LimitsExceeded,
    ModelError,
    Submitted,
)
from mini_agent.models import litellm_model

SENTINEL = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"


def _truncate(text: str, limit: int = 8000) -> str:
    """Cap output length so one big cat can't blow the context window."""
    if len(text) <= limit:
        return text
    return text[:4000] + "\n[... truncated ...]\n" + text[-4000:]


def _preview(text: str, lines: int = 3, width: int = 120) -> str:
    shown = [ln[:width] for ln in text.strip().splitlines()[:lines]]
    return " | ".join(shown) if shown else "(no output)"


def run(
    task: str,
    max_steps: int = 20,
    max_cost_usd: float = 5.0,
    max_consecutive_format_errors: int = 3,
    max_total_tokens: int = 150_000,  # cost_usd stays 0.0 on custom endpoints (probe-verified), so tokens are the real budget
    output_path: Path | None = None,
) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    steps = 0
    total_cost = 0.0
    total_tokens = 0
    format_errors = 0
    exit_status = "unknown"

    def _snapshot():
        """Dump current state; called every round (crash safety) and once at the end."""
        if output_path is None:
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "task": task,
                    "exit_status": exit_status,
                    "info": {
                        "steps": steps,
                        "total_cost_usd": total_cost,
                        "total_tokens": total_tokens,
                    },
                    "messages": messages,
                },
                ensure_ascii=False,  # keep Chinese readable, not \uXXXX
                indent=2,
            )
        )

    while True:
        try:
            if steps >= max_steps:
                raise LimitsExceeded(
                    {"role": "exit", "content": f"Stopped: max steps ({max_steps}) reached."}
                )
            try:
                reply, usage = litellm_model.chat(messages)
            except Exception as e:
                raise ModelError(
                    {"role": "exit", "content": f"Stopped: model call failed: {e}"}
                ) from e
            steps += 1
            total_cost += usage["cost_usd"]
            total_tokens += usage["prompt_tokens"] + usage["completion_tokens"]
            if total_tokens > max_total_tokens:
                raise LimitsExceeded(
                    {
                        "role": "exit",
                        "content": f"Stopped: token limit ({max_total_tokens}) exceeded ({total_tokens}).",
                    }
                )
            if total_cost > max_cost_usd:
                raise LimitsExceeded(
                    {
                        "role": "exit",
                        "content": f"Stopped: cost limit ${max_cost_usd} exceeded (${total_cost:.4f}).",
                    }
                )

            # reply goes into history BEFORE parsing — format errors must stay
            # visible so the model can see and fix its own mistake
            messages.append({"role": "assistant", "content": reply})

            try:
                command = litellm_model.parse_action(reply)
                format_errors = 0
            except FormatError as e:
                print(f"[step {steps}] format error: {_preview(e.messages[0]['content'])}")
                format_errors += 1
                if format_errors >= max_consecutive_format_errors:
                    raise LimitsExceeded(
                        {
                            "role": "exit",
                            "content": f"Stopped: {format_errors} consecutive format errors.",
                        }
                    ) from e
                raise  # FormatError already carries the feedback message

            print(f"[step {steps}] $ {command}")
            obs = local.execute(command)
            print(f"[step {steps}] -> rc={obs['returncode']} {_preview(obs['output'])}")

            messages.append({
                "role": "user",
                "content": (
                    f"<returncode>{obs['returncode']}</returncode>\n"
                    f"<output>\n{_truncate(obs['output'])}\n</output>"
                ),
            })

            # sentinel: only a clean run whose first output line is the sentinel ends the task
            if obs["returncode"] == 0 and obs["output"].strip().splitlines()[:1] == [SENTINEL]:
                raise Submitted(
                    {"role": "exit", "content": f"Task completed successfully after {steps} steps."}
                )
        except InterruptAgentFlow as e:
            messages.extend(e.messages)
            if isinstance(e, Submitted):
                exit_status = "success"
            elif isinstance(e, ModelError):
                exit_status = "model_error"
            else:
                exit_status = "limits_exceeded"

        # all paths converge here — every round is on disk, including error rounds
        _snapshot()

        # the ONLY exit signal: an exit message in history
        if messages[-1]["role"] == "exit":
            break

    return {"exit_status": exit_status, "messages": messages}


