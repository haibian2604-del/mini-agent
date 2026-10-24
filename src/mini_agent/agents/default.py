"""The agent loop: model <-> shell, linear history, append-only."""

from mini_agent.config.prompts import SYSTEM_PROMPT
from mini_agent.environments import local
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


def run(task: str, max_steps: int = 20) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    for step in range(1, max_steps + 1):
        # 1. model reply goes into history BEFORE parsing — format errors
        #    must stay visible so the model can see and fix its own mistake
        reply, _ = litellm_model.chat(messages)  # usage accounting lands in step 11
        messages.append({"role": "assistant", "content": reply})

        try:
            command = litellm_model.parse_action(reply)
        except ValueError as e:
            print(f"[step {step}] format error: {_preview(str(e))}")
            messages.append({"role": "user", "content": str(e)})
            continue

        print(f"[step {step}] $ {command}")
        obs = local.execute(command)
        print(f"[step {step}] -> rc={obs['returncode']} {_preview(obs['output'])}")

        messages.append({
            "role": "user",
            "content": (
                f"<returncode>{obs['returncode']}</returncode>\n"
                f"<output>\n{_truncate(obs['output'])}\n</output>"
            ),
        })

        # sentinel: only a clean run whose first output line is the sentinel ends the task
        if obs["returncode"] == 0 and obs["output"].strip().splitlines()[:1] == [SENTINEL]:
            return {"exit_status": "success", "messages": messages}

    return {"exit_status": "max_steps_reached", "messages": messages}


if __name__ == "__main__":
    # Offline loop test: fake the model, script a three-act play.
    _NO_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
    replies = iter([
        ("THOUGHT: 故意格式错误，没有bash块", _NO_USAGE),                                        # 1: format error
        ("THOUGHT: 先看看\n```bash\necho hello\n```", _NO_USAGE),                                # 2: real command
        ("THOUGHT: 完事了\n```bash\necho COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n```", _NO_USAGE),  # 3: done
    ])
    litellm_model.chat = lambda messages: next(replies)  # swap in the fake

    result = run("测试任务")

    assert result["exit_status"] == "success", result["exit_status"]

    user_msgs = [m["content"] for m in result["messages"] if m["role"] == "user"]
    # 2nd user msg = format error fed back (self-correction loop)
    assert "Format error" in user_msgs[1], user_msgs[1]
    # 3rd user msg = observation with hello (execution loop)
    assert "hello" in user_msgs[2], user_msgs[2]

    print("✅ agent loop self-test passed (fake model)")
