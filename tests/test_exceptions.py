"""Tests for mini_agent.exceptions — polymorphic catch + message carrying."""

import pytest

from mini_agent.exceptions import FormatError, InterruptAgentFlow, LimitsExceeded, Submitted


def test_submitted_messages_carry_and_catch_by_base():
    err = Submitted(
        {"role": "exit", "content": "done"},
        {"role": "user", "content": "extra"},
    )
    with pytest.raises(InterruptAgentFlow) as exc_info:
        raise err
    assert len(exc_info.value.messages) == 2
    assert exc_info.value.messages[0]["role"] == "exit"


@pytest.mark.parametrize("cls", [Submitted, LimitsExceeded, FormatError])
def test_all_subclasses_are_interrupts(cls):
    assert issubclass(cls, InterruptAgentFlow)
