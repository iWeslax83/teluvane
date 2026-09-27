from teluvane.schema import Event
from teluvane.tribunal import _events_to_text


def test_erased_events_are_marked_not_shown():
    e = Event(
        agent_id="a", session_id="s", kind="tool_call", tool="t", intent="secret words", erased=True
    )
    e.seq = 4
    text = _events_to_text([e])
    assert "[payload erased]" in text and "secret words" not in text
