from teluvane.schema import Verdict


def test_erase_removes_content_but_chain_and_hashes_survive(store, org, add_events):
    add_events(org, 3)
    before = store.canonical_events(org, "s1")
    store.add_verdict(
        org,
        Verdict(
            session_id="s1",
            rule_id="r",
            severity="high",
            violation=True,
            confidence=0.9,
            evidence_seqs=[1],
            rationale="jane@example.com leaked",
            framework_ref="x",
        ),
    )
    res = store.erase_payloads(org, "s1", requested_by="u1", reason="art 17 request")
    assert res == {"erased": 3, "already_erased": 0, "legacy_unerasable": 0}
    events = store.events(org, "s1")
    assert all(e.erased and e.intent == "" and e.args == {} for e in events)
    assert store.canonical_events(org, "s1") == before
    assert store.verify_chain(org, "s1")
    assert "jane@example.com" not in store.verdicts(org, "s1")[0].rationale
    assert store.payload_openings(org, "s1") == []
    assert store.verify_report(org, "s1") == {
        "chain_intact": True,
        "erased_events": 3,
        "unexplained_erasures": 0,
    }


def test_erasing_after_v1_then_v2_events_keeps_the_chain(store, org, add_events, monkeypatch):
    monkeypatch.setenv("TELUVANE_EVENT_HASH_VERSION", "1")
    add_events(org, 2)
    monkeypatch.delenv("TELUVANE_EVENT_HASH_VERSION")
    add_events(org, 2)
    assert store.erase_payloads(org, "s1", "u1") == {
        "erased": 2,
        "already_erased": 0,
        "legacy_unerasable": 2,
    }
    assert store.verify_chain(org, "s1")


def test_partial_erase_and_idempotence(store, org, add_events):
    evs = add_events(org, 3)
    assert store.erase_payloads(org, "s1", "u1", seqs=[evs[0].seq])["erased"] == 1
    assert [e.erased for e in store.events(org, "s1")] == [True, False, False]
    assert store.verify_chain(org, "s1")
    again = store.erase_payloads(org, "s1", "u1")
    assert again["erased"] == 2 and again["already_erased"] == 1
    assert store.erase_payloads(org, "s1", "u1")["erased"] == 0


def test_silent_payload_deletion_is_reported_as_unexplained(store, org, add_events):
    add_events(org, 2)
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM event_payloads WHERE org_id=%s", (org,))
        conn.commit()
    report = store.verify_report(org, "s1")
    assert report["chain_intact"] and report["erased_events"] == 2
    assert report["unexplained_erasures"] == 2


def test_erase_is_tenant_scoped(store, org, add_events):
    add_events("org1", 1, session="shared")
    add_events("org2", 1, session="shared")
    store.erase_payloads("org2", "shared", "u2")
    assert not store.events("org1", "shared")[0].erased
    assert store.events("org2", "shared")[0].erased


def test_legacy_v1_events_are_reported_not_erased(store, org, add_events, monkeypatch):
    monkeypatch.setenv("TELUVANE_EVENT_HASH_VERSION", "1")
    add_events(org, 2)
    assert store.verify_chain(org, "s1")
    res = store.erase_payloads(org, "s1", "u1")
    assert res == {"erased": 0, "already_erased": 0, "legacy_unerasable": 2}
    assert store.events(org, "s1")[0].intent.startswith("email jane")
