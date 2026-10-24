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


if __name__ == "__main__":
    # 1. one bash block -> command extracted
    cmd = parse_action("THOUGHT: look around first.\n\n```bash\nls -la src/\n```\n")
    assert cmd == "ls -la src/", cmd

    # 2. two bash blocks -> must raise ValueError mentioning the count
    try:
        parse_action("```bash\nls\n```\nthen\n```bash\npwd\n```")
    except ValueError as e:
        assert "found 2" in str(e), e
    else:
        raise AssertionError("two bash blocks should raise ValueError")

    # 3. zero bash blocks -> must raise too
    try:
        parse_action("THOUGHT only, no command")
    except ValueError as e:
        assert "found 0" in str(e), e
    else:
        raise AssertionError("zero bash blocks should raise ValueError")

    # 4. chat() accounting, offline: fake the litellm completion call
    class _Msg:
        content = "hi"
    class _Choice:
        message = _Msg()
    class _Usage:
        prompt_tokens = 10
        completion_tokens = 5
    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    completion = lambda **kw: _Resp()  # noqa: F811 - shadow the real one
    content, usage = chat([{"role": "user", "content": "ping"}])
    assert content == "hi"
    assert usage == {"prompt_tokens": 10, "completion_tokens": 5, "cost_usd": 0.0}, usage

    print("✅ litellm_model self-test passed")
