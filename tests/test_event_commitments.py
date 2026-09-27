import json

from teluvane import commitments
from teluvane.schema import Event


def test_v2_event_keeps_plaintext_out_of_the_events_row(store, org, add_events):
    (e,) = add_events(org, 1)
    assert e.hash_version == 2 and e.payload_commitment
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT intent, args, output, approved_by FROM events WHERE seq=%s", (e.seq,))
        assert cur.fetchone() == ("", {}, "", None)
    got = store.events(org, "s1")[0]
    assert got.intent == "email jane@example.com step 0"
    assert got.args == {"ssn": "078-05-1120"} and got.approved_by == "human:u1"
    assert not got.erased


def test_canonical_v2_contains_no_personal_content(store, org, add_events):
    add_events(org, 2)
    for row in store.canonical_events(org, "s1"):
        assert "jane@example.com" not in row["canonical"]
        assert "078-05-1120" not in row["canonical"]
        assert json.loads(row["canonical"])["v"] == 2


def test_identical_payloads_get_different_commitments(store, org):
    make = lambda: Event(agent_id="a", session_id="s2", kind="llm_call", intent="same")  # noqa: E731
    first, second = store.append(org, make()), store.append(org, make())
    assert first.payload_commitment != second.payload_commitment


def test_verify_detects_payload_tampering(store, org, add_events):
    add_events(org, 3)
    assert store.verify_chain(org, "s1")
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE event_payloads SET payload = replace(payload, 'step 1', 'step X') "
            "WHERE seq = (SELECT seq FROM events WHERE session_id='s1' "
            "ORDER BY seq OFFSET 1 LIMIT 1)"
        )
        conn.commit()
    assert not store.verify_chain(org, "s1")


def test_verify_detects_tampering_with_the_clear_fields(store, org, add_events):
    add_events(org, 2)
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE events SET tool='rm' WHERE session_id='s1'")
        conn.commit()
    assert not store.verify_chain(org, "s1")


def test_v1_then_v2_in_one_session_verifies(store, org, add_events, monkeypatch):
    monkeypatch.setenv("TELUVANE_EVENT_HASH_VERSION", "1")
    add_events(org, 2)
    monkeypatch.delenv("TELUVANE_EVENT_HASH_VERSION")
    add_events(org, 2)
    assert [e.hash_version for e in store.events(org, "s1")] == [1, 1, 2, 2]
    assert store.verify_chain(org, "s1")


def test_verify_chain_across_sessions_is_per_session(store, org, add_events):
    add_events(org, 2, session="a")
    add_events(org, 2, session="b")
    assert store.verify_chain(org)


def test_commitment_can_be_recomputed_from_an_opening(store, org, add_events):
    (e,) = add_events(org, 1)
    (opening,) = store.payload_openings(org, "s1")
    assert commitments.commit(opening["salt"], opening["payload"]) == e.payload_commitment
