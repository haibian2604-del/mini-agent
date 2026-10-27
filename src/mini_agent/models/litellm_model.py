"""All LLM interaction: one chat() call via litellm, one parse_action() extractor."""

import os
import re
import time

from dotenv import load_dotenv
from litellm import completion, completion_cost
from litellm.exceptions import AuthenticationError

from mini_agent.exceptions import FormatError

load_dotenv()

MAX_RETRIES = 3
RETRY_INTERVAL = 2  # seconds


def _usage(response) -> dict:
    """Token/cost accounting; cost falls back to 0.0 when the price is unknown."""
    usage = getattr(response, "usage", None)
    try:
        cost = completion_cost(response)
    except Exception:
        cost = 0.0  # custom endpoints / unknown models have no price in the map
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
        "completion_tokens": getattr(usage, "completion_tokens", 0),
        "cost_usd": cost,
    }


def chat(messages: list[dict], model: str) -> tuple[str, dict]:
    """One LLM call with retry (3x, 2s apart); returns (content, usage).

    AuthenticationError and KeyboardInterrupt are never retried — a bad key
    will not fix itself, and the user pressing Ctrl-C means now.
    Model is an explicit argument — no hidden os.environ reads here.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = completion(
                model=model,
                messages=messages,
                api_key=os.getenv("API_KEY"),
                api_base=os.getenv("BASE_URL") or None,
            )
            break
        except (AuthenticationError, KeyboardInterrupt):
            raise
        except Exception:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_INTERVAL)
    return response.choices[0].message.content or "", _usage(response)


_ACTION_RE = re.compile(r"```([A-Za-z0-9_+-]*)[^\S\n]*\n(.*?)```", re.DOTALL)


def parse_action(text: str) -> str:
    """Extract the single bash command from a model reply.

    Accepts blocks labeled ```bash and unlabeled blocks (models often drop the
    label). Other language labels (```python etc.) are ignored entirely — they
    can't run in a bash shell, so they don't count as candidate actions.

    Raises FormatError carrying the feedback message (fed back to the model
    for self-correction) when the actionable-block count is not exactly 1.
    """
    candidates = [
        body for lang, body in _ACTION_RE.findall(text) if lang.lower() in ("", "bash")
    ]
    if len(candidates) != 1:
        raise FormatError({
            "role": "user",
            "content": (
                f"Format error: expected exactly 1 bash code block, found {len(candidates)}. "
                "Reply with a short THOUGHT and exactly one ```bash block containing one command."
            ),
        })
    return candidates[0].strip()


