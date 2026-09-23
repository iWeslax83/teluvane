# teluvane/teluvane/mcp_server.py
"""MCP server that lets any MCP-compatible agent (Claude Desktop, Claude Code, or anything
else speaking the protocol) auto-log its actions to TELUVANE without writing recorder calls
into the agent itself.

Configure via env vars and point an MCP client at this process over stdio:
  TELUVANE_URL       base URL of the TELUVANE API (default http://localhost:8900)
  TELUVANE_API_KEY   an org API key, from the dashboard's API keys page (required)
  TELUVANE_AGENT_ID  label recorded on every event (default "mcp-agent")

Run directly:  python -m teluvane.mcp_server
Or as a Claude Desktop MCP server, in claude_desktop_config.json:
  {"mcpServers": {"teluvane": {"command": "python", "args": ["-m", "teluvane.mcp_server"],
   "env": {"TELUVANE_URL": "...", "TELUVANE_API_KEY": "tv_live_..."}}}}

One process = one recorded session by default (a fresh session_id generated at startup), so a
whole Claude Desktop conversation lands in TELUVANE as a single auditable session. Pass an
explicit session_id to any tool to record into a different one instead.
"""

import os
import uuid

from mcp.server.fastmcp import FastMCP

from .recorder import TeluvaneRecorder

AGENT_ID = os.environ.get("TELUVANE_AGENT_ID", "mcp-agent")
BASE_URL = os.environ.get("TELUVANE_URL", "http://localhost:8900")
API_KEY = os.environ.get("TELUVANE_API_KEY")
DEFAULT_SESSION_ID = "mcp-" + uuid.uuid4().hex[:12]

mcp = FastMCP("teluvane")


def _recorder(session_id: str | None) -> TeluvaneRecorder:
    if not API_KEY:
        raise RuntimeError("TELUVANE_API_KEY is not set")
    return TeluvaneRecorder(
        agent_id=AGENT_ID,
        session_id=session_id or DEFAULT_SESSION_ID,
        base_url=BASE_URL,
        api_key=API_KEY,
    )


@mcp.tool()
def record_llm_call(
    intent: str,
    output: str = "",
    session_id: str | None = None,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> str:
    """Record that the agent made an LLM call. `intent` should say why in one sentence,
    since that's what the tribunal audits against, not the raw prompt/completion. Pass
    model + input_tokens/output_tokens when known, for cost tracking in /stats/usage."""
    _recorder(session_id).record_llm_call(
        intent=intent,
        output=output,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    return f"recorded llm_call to session {session_id or DEFAULT_SESSION_ID}"


@mcp.tool()
def record_tool_call(
    tool: str,
    args: dict,
    intent: str = "",
    approved_by: str | None = None,
    session_id: str | None = None,
) -> str:
    """Record that the agent invoked a tool. Set approved_by (e.g. a user id, or "auto" for
    an allowlisted action) when a human or policy explicitly authorized this call."""
    _recorder(session_id).record_tool_call(
        tool=tool, args=args, intent=intent, approved_by=approved_by
    )
    return f"recorded tool_call({tool}) to session {session_id or DEFAULT_SESSION_ID}"


@mcp.tool()
def record_tool_result(tool: str, output: str, session_id: str | None = None) -> str:
    """Record the result of a tool call previously recorded with record_tool_call."""
    _recorder(session_id).record_tool_result(tool=tool, output=output)
    return f"recorded tool_result({tool}) to session {session_id or DEFAULT_SESSION_ID}"


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
