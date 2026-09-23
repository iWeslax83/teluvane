# teluvane/tests/test_recorder.py
from teluvane.recorder import TeluvaneRecorder
from teluvane.store import Store


def test_recorder_writes_tool_events():
    s = Store()
    rec = TeluvaneRecorder(agent_id="demo", session_id="s1", store=s, org_id="orgT")
    rec.record_tool_call(tool="send_email", args={"to": "a@b.com"}, intent="notify user")
    rec.record_tool_result(tool="send_email", output="sent")
    evs = s.events("orgT", "s1")
    assert [e.kind for e in evs] == ["tool_call", "tool_result"]
    assert evs[0].tool == "send_email" and evs[0].intent == "notify user"


import httpx
import respx


@respx.mock
def test_http_recorder_sends_api_key_header():
    route = respx.post("http://api.test/events").mock(return_value=httpx.Response(200, json={}))
    rec = TeluvaneRecorder(
        agent_id="a", session_id="s", base_url="http://api.test", api_key="tv_live_xyz"
    )
    rec.record_llm_call(intent="hi")
    assert route.called
    assert route.calls[0].request.headers["authorization"] == "Bearer tv_live_xyz"
