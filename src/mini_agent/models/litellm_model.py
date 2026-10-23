"""All LLM interaction: one chat() call via litellm, one parse_action() extractor."""

import os
import re

from dotenv import load_dotenv
from litellm import completion

load_dotenv()

MODEL_NAME = "zhipuai/glm-4.6"

# MODEL/BASE_URL come from .env (proven working: openai/<model> + BASE_URL).
# MODEL_NAME is the fallback when .env has no MODEL.
def chat(messages: list[dict]) -> str:
    """One LLM call; returns message content ('' if the model returned None)."""
    response = completion(
        model=os.getenv("MODEL", MODEL_NAME),
        messages=messages,
        api_key=os.getenv("API_KEY"),
        api_base=os.getenv("BASE_URL") or None,
    )
    return response.choices[0].message.content or ""


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

    print("✅ litellm_model self-test passed")
