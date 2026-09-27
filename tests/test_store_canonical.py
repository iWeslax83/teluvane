import hashlib
import json
import os
import pathlib

from teluvane.schema import Event
from teluvane.store import _event_canonical, _event_digest

VECTORS = pathlib.Path(__file__).parent / "fixtures" / "chain_vectors.json"
VECTORS_V2 = pathlib.Path(__file__).parent / "fixtures" / "chain_vectors_v2.json"


def test_canonical_string_hashes_to_the_same_digest():
    e = Event(
        agent_id="a",
        session_id="s",
        kind="tool_call",
        tool="shell",
        args={"cmd": "ls", "u": "é"},
        intent="look",
    )
    e.org_id = "org1"
    canon = _event_canonical("GENESIS", e)
    assert hashlib.sha256(canon.encode("utf-8")).hexdigest() == _event_digest("GENESIS", e)
    assert json.loads(canon)["prev"] == "GENESIS"


def test_canonical_events_roundtrip(store):
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO orgs(id,name,owner_user_id) VALUES('org1','o','u') ON CONFLICT DO NOTHING"
        )
        conn.commit()
    for i in range(3):
        store.append(
            "org1", Event(agent_id="a", session_id="s1", kind="llm_call", intent=f"step {i}")
        )
    rows = store.canonical_events("org1", "s1")
    assert [r["seq"] for r in rows] == sorted(r["seq"] for r in rows)
    prev = "GENESIS"
    for r in rows:
        assert hashlib.sha256(r["canonical"].encode("utf-8")).hexdigest() == r["hash"]
        assert json.loads(r["canonical"])["prev"] == prev
        prev = r["hash"]

    # Regenerate the fixture the TS port checks against only on request; a plain
    # pytest run must not dirty the working tree.
    if os.environ.get("REGEN_ANCHOR_VECTORS"):
        VECTORS.write_text(json.dumps({"events": rows}, indent=2, ensure_ascii=False))


def test_v2_canonical_roundtrip_and_vectors(store):
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO orgs(id,name,owner_user_id) VALUES('org1','o','u') ON CONFLICT DO NOTHING"
        )
        conn.commit()
    for i in range(3):
        store.append(
            "org1", Event(agent_id="a", session_id="s1", kind="llm_call", intent=f"step {i}")
        )
    rows = store.canonical_events("org1", "s1")
    prev = "GENESIS"
    for r in rows:
        parsed = json.loads(r["canonical"])
        assert parsed["v"] == 2 and parsed["prev"] == prev and "intent" not in parsed
        assert hashlib.sha256(r["canonical"].encode("utf-8")).hexdigest() == r["hash"]
        prev = r["hash"]
    if os.environ.get("REGEN_ANCHOR_VECTORS"):
        VECTORS_V2.write_text(json.dumps({"events": rows}, indent=2, ensure_ascii=False))
