"""Control-flow exceptions: each carries the messages that must enter history."""


class InterruptAgentFlow(Exception):
    """Base: catch this one type to handle every interrupt; e.messages go into history."""

    def __init__(self, *messages: dict):
        self.messages = messages
        super().__init__()


class Submitted(InterruptAgentFlow):
    """Task finished (sentinel hit)."""


class LimitsExceeded(InterruptAgentFlow):
    """A limit was exhausted: steps, cost, or consecutive format errors."""


class FormatError(InterruptAgentFlow):
    """Model reply violated the format; error message is fed back for self-correction."""


if __name__ == "__main__":
    try:
        raise Submitted(
            {"role": "exit", "content": "done"},
            {"role": "user", "content": "extra"},
        )
    except InterruptAgentFlow as e:
        assert len(e.messages) == 2
        assert e.messages[0]["role"] == "exit"
    print("ok")
