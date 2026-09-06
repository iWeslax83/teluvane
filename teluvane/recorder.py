# teluvane/teluvane/recorder.py
from typing import Any, Optional
import httpx
from .schema import Event
from .store import Store

class TeluvaneRecorder:
    """Capture agent steps. Pass a Store for in-process use, or base_url to POST over HTTP."""
    def __init__(self, agent_id: str, session_id: str,
                 store: Optional[Store] = None, base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 org_id: str = "default"):
        self.agent_id = agent_id
        self.session_id = session_id
        self.store = store
        self.base_url = base_url.rstrip("/") if base_url else None
        self.api_key = api_key
        self.org_id = org_id

    def _emit(self, **kw: Any) -> None:
        e = Event(agent_id=self.agent_id, session_id=self.session_id, **kw)
        if self.store is not None:
            self.store.append(self.org_id, e)
        elif self.base_url:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            resp = httpx.post(f"{self.base_url}/events", json=e.model_dump(),
                              headers=headers, timeout=10)
            # A silently dropped event defeats the point of an audit log: surface a
            # bad key / server error to the caller instead of reporting success.
            resp.raise_for_status()
        else:
            raise RuntimeError("Recorder needs either store or base_url")

    def record_llm_call(self, intent: str, output: str = "", model: Optional[str] = None,
                        input_tokens: Optional[int] = None, output_tokens: Optional[int] = None) -> None:
        self._emit(kind="llm_call", intent=intent, output=output, model=model,
                   input_tokens=input_tokens, output_tokens=output_tokens)

    def record_tool_call(self, tool: str, args: dict, intent: str = "",
                         approved_by: Optional[str] = None) -> None:
        self._emit(kind="tool_call", tool=tool, args=args, intent=intent,
                   approved_by=approved_by)

    def record_tool_result(self, tool: str, output: str) -> None:
        self._emit(kind="tool_result", tool=tool, output=output)
