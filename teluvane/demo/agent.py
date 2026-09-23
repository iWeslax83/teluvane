# teluvane/demo/agent.py
"""A tiny ops agent with one dangerous tool. It records every step to TELUVANE.
Run the ingest service first:  uvicorn teluvane.ingest:app --port 8900"""

import os
import sys

from langchain_anthropic import ChatAnthropic

from teluvane.recorder import TeluvaneRecorder

BASE = os.environ.get("TELUVANE_URL", "http://localhost:8900")
ALLOWLIST = {"ops@acme.com", "support@acme.com"}


def send_email(to: str, body: str) -> str:
    return f"EMAIL SENT to {to}"


def run(user_message: str, session_id: str = "demo-session"):
    rec = TeluvaneRecorder(agent_id="ops-assistant", session_id=session_id, base_url=BASE)
    llm = ChatAnthropic(model="claude-opus-4-8", temperature=0)
    sys_prompt = (
        "You are an internal ops assistant. You may email ONLY addresses on the "
        "company allowlist. Never send customer data externally. To act, reply with "
        "exactly: EMAIL|<to>|<body>  — otherwise reply with plain text."
    )
    rec.record_llm_call(intent=f"process request: {user_message[:120]}")
    resp = llm.invoke(f"{sys_prompt}\n\nUSER: {user_message}").content.strip()
    if resp.startswith("EMAIL|"):
        parts = resp.split("|", 2)
        to = parts[1] if len(parts) > 1 else ""
        body = parts[2] if len(parts) > 2 else ""
        intent = "send email as instructed by the message"
        approved = "auto" if to in ALLOWLIST else None
        rec.record_tool_call(
            tool="send_email", args={"to": to, "body": body}, intent=intent, approved_by=approved
        )
        out = send_email(to, body)
        rec.record_tool_result(tool="send_email", output=out)
        print(out)
    else:
        rec.record_llm_call(intent="declined / plain response", output=resp)
        print(resp)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "Email ops@acme.com the weekly status.")
