"""Control-flow exceptions: each carries the messages that must enter history."""


class InterruptAgentFlow(Exception):
    """Base: catch this one type to handle every interrupt; e.messages go into history."""

    def __init__(self, *messages: dict):
        self.messages = messages
        super().__init__()


class Submitted(InterruptAgentFlow):
    """Task finished (sentinel hit)."""


class LimitsExceeded(InterruptAgentFlow):
    """A limit was exhausted: steps, tokens, cost, or consecutive format errors."""


class ModelError(InterruptAgentFlow):
    """Model call failed for good (retries exhausted); distinct from limits."""


class FormatError(InterruptAgentFlow):
    """Model reply violated the format; error message is fed back for self-correction."""
