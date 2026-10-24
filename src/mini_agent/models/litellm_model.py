"""All LLM interaction: one chat() call via litellm, one parse_action() extractor."""

import os
import re

from dotenv import load_dotenv
from litellm import completion, completion_cost

load_dotenv()


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


def chat(messages: list[dict]) -> tuple[str, dict]:
    """One LLM call; returns (content, usage). Content is '' if the model returned None."""
    response = completion(
        model=os.environ["MODEL"],
        messages=messages,
        api_key=os.getenv("API_KEY"),
        api_base=os.getenv("BASE_URL") or None,
    )
    return response.choices[0].message.content or "", _usage(response)


_ACTION_RE = re.compile(r"```bash\s*(.*?)```", re.DOTALL)


def parse_action(text: str) -> str:
    """Extract the single bash command from a model reply.

    Raises ValueError (fed back to the model for self-correction) when the
    reply does not contain exactly one ```bash block.
    """
    blocks = _ACTION_RE.findall(text)
    if len(blocks) != 1:
        raise ValueError(
            f"Format error: expected exactly 1 bash code block, found {len(blocks)}. "
            "Reply with a short THOUGHT and exactly one ```bash block containing one command."
        )
    return blocks[0].strip()


