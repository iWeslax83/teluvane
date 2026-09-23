import os

os.environ["TELUVANE_API_KEY"] = "tv_live_test"
os.environ["TELUVANE_URL"] = "http://localhost:8900"
os.environ["TELUVANE_AGENT_ID"] = "test-agent"

import httpx

from teluvane import mcp_server


def _stub_post(calls):
    def _post(url, json, headers, timeout):
        calls.append((url, json, headers))
        return httpx.Response(200, json={}, request=httpx.Request("POST", url))

    return _post


def test_record_llm_call_posts_the_right_event(monkeypatch):
    calls = []
    monkeypatch.setattr(httpx, "post", _stub_post(calls))

    mcp_server.record_llm_call(intent="summarize the ticket", output="done")

    assert len(calls) == 1
    url, body, headers = calls[0]
    assert url == "http://localhost:8900/events"
    assert headers["Authorization"] == "Bearer tv_live_test"
    assert body["kind"] == "llm_call" and body["intent"] == "summarize the ticket"
    assert body["agent_id"] == "test-agent"
    assert body["session_id"] == mcp_server.DEFAULT_SESSION_ID


def test_record_tool_call_and_result_use_explicit_session_id(monkeypatch):
    raw = []
    monkeypatch.setattr(httpx, "post", _stub_post(raw))

    mcp_server.record_tool_call(
        tool="send_email",
        args={"to": "x@y.com"},
        intent="notify",
        approved_by="auto",
        session_id="custom-sess",
    )
    mcp_server.record_tool_result(tool="send_email", output="sent", session_id="custom-sess")

    calls = [body for _url, body, _headers in raw]
    assert len(calls) == 2
    assert calls[0]["kind"] == "tool_call" and calls[0]["session_id"] == "custom-sess"
    assert calls[0]["approved_by"] == "auto"
    assert calls[1]["kind"] == "tool_result" and calls[1]["output"] == "sent"


def test_requires_api_key(monkeypatch):
    monkeypatch.setattr(mcp_server, "API_KEY", None)
    try:
        mcp_server.record_llm_call(intent="x")
        assert False, "expected an error"
    except RuntimeError as e:
        assert "TELUVANE_API_KEY" in str(e)
