import pytest

from teluvane.schema import Event, Verdict


def _ev(session_id="s1", **kw):
    return Event(agent_id="a", session_id=session_id, kind="tool_call", **kw)


def _vd(session_id="s1"):
    return Verdict(
        session_id=session_id,
        rule_id="data_exfiltration",
        severity="critical",
        violation=True,
        confidence=0.9,
        evidence_seqs=[1],
    )


def test_append_assigns_seq_hash_and_org(store):
    e = store.append("orgA", _ev())
    assert e.seq is not None and e.hash and e.prev_hash == "GENESIS" and e.org_id == "orgA"


def test_chain_links_within_org_session(store):
    e1 = store.append("orgA", _ev())
    e2 = store.append("orgA", _ev())
    assert e2.prev_hash == e1.hash


def test_chain_is_independent_per_org(store):
    store.append("orgA", _ev(session_id="s1"))
    b1 = store.append("orgB", _ev(session_id="s1"))
    assert b1.prev_hash == "GENESIS"  # orgB starts its own genesis, not chained to orgA


def test_events_are_scoped_to_org(store):
    store.append("orgA", _ev())
    store.append("orgB", _ev())
    evs = store.events("orgA")
    assert len(evs) == 1 and all(e.org_id == "orgA" for e in evs)


def test_tenant_isolation_no_cross_read(store):  # <-- GATE TEST
    store.append("orgA", _ev(session_id="secret"))
    assert store.events("orgB", session_id="secret") == []


def test_verify_chain_true_for_intact_org_chain(store):
    store.append("orgA", _ev())
    store.append("orgA", _ev())
    assert store.verify_chain("orgA") is True


def test_verdicts_scoped_to_org(store):
    store.append("orgA", _ev())
    store.add_verdict("orgA", _vd())
    assert len(store.verdicts("orgA")) == 1
    assert store.verdicts("orgB") == []


def test_assert_scoped_rejects_empty_org(store):
    with pytest.raises(ValueError):
        store._assert_scoped("", "SELECT 1 FROM events WHERE org_id=%s")


def test_assert_scoped_rejects_unscoped_sql(store):
    with pytest.raises(ValueError):
        store._assert_scoped("orgA", "SELECT 1 FROM events")


@pytest.mark.parametrize(
    "call",
    [
        lambda s: s.events(""),
        lambda s: s.verdicts(""),
        lambda s: s.verify_chain(""),
        lambda s: s.append("", _ev()),
        lambda s: s.add_verdict("", _vd()),
        lambda s: s.sessions(""),
        lambda s: s.usage(""),
    ],
)
def test_every_public_method_requires_org(store, call):
    with pytest.raises(ValueError):
        call(store)


def test_sessions_search_filters_by_substring(store):
    store.append("orgA", _ev(session_id="alpha-1"))
    store.append("orgA", _ev(session_id="beta-1"))
    names = {s["session_id"] for s in store.sessions("orgA", q="alpha")}
    assert names == {"alpha-1"}


def test_violation_trend_is_zero_filled_and_counts_only_violations(store):
    store.append("orgA", _ev())
    store.add_verdict("orgA", _vd())  # a violation today
    store.add_verdict(
        "orgA",
        Verdict(
            session_id="s1",
            rule_id="r2",
            severity="low",
            violation=False,
            confidence=0.1,
            evidence_seqs=[],
        ),
    )  # not a violation
    trend = store.violation_trend("orgA", days=7)
    assert len(trend) == 7  # zero-filled for every day in the window
    assert (
        trend[-1]["violations"] == 1
    )  # today: 1 confirmed violation, the non-violation doesn't count
    assert all(d["violations"] == 0 for d in trend[:-1])


def test_append_computes_cost_from_known_model(store):
    e = store.append(
        "orgA",
        Event(
            agent_id="a",
            session_id="s1",
            kind="llm_call",
            model="claude-sonnet-5",
            input_tokens=1000,
            output_tokens=1000,
        ),
    )
    assert e.cost_usd == pytest.approx(0.003 + 0.015)


def test_append_leaves_cost_none_for_unknown_model(store):
    e = store.append(
        "orgA",
        Event(
            agent_id="a",
            session_id="s1",
            kind="llm_call",
            model="some-unknown-model",
            input_tokens=1000,
            output_tokens=1000,
        ),
    )
    assert e.cost_usd is None


def test_append_respects_explicit_cost_usd(store):
    e = store.append(
        "orgA",
        Event(
            agent_id="a",
            session_id="s1",
            kind="llm_call",
            model="claude-sonnet-5",
            input_tokens=1000,
            output_tokens=1000,
            cost_usd=1.23,
        ),
    )
    assert e.cost_usd == 1.23


def test_cost_is_excluded_from_hash_chain():
    """Token/cost metadata must not affect the digest, so pre-migration chains (which never
    had these fields) keep verifying after the columns were added."""
    from teluvane.store import _event_digest

    base = Event(agent_id="a", session_id="s1", kind="llm_call", ts="2026-01-01T00:00:00+00:00")
    with_cost = base.model_copy(
        update={
            "model": "claude-sonnet-5",
            "input_tokens": 1000,
            "output_tokens": 1000,
            "cost_usd": 0.018,
        }
    )
    assert _event_digest("GENESIS", base) == _event_digest("GENESIS", with_cost)


def test_usage_is_zero_filled_and_sums_tokens_and_cost(store):
    store.append(
        "orgA",
        Event(
            agent_id="a",
            session_id="s1",
            kind="llm_call",
            model="claude-sonnet-5",
            input_tokens=1000,
            output_tokens=1000,
        ),
    )
    usage = store.usage("orgA", days=7)
    assert len(usage) == 7
    assert usage[-1]["input_tokens"] == 1000
    assert usage[-1]["output_tokens"] == 1000
    assert usage[-1]["cost_usd"] == pytest.approx(0.018)
    assert all(d["cost_usd"] == 0 for d in usage[:-1])


def test_usage_scoped_to_org(store):
    store.append(
        "orgA",
        Event(
            agent_id="a",
            session_id="s1",
            kind="llm_call",
            model="claude-sonnet-5",
            input_tokens=1000,
            output_tokens=1000,
        ),
    )
    usage_b = store.usage("orgB", days=1)
    assert usage_b[0]["cost_usd"] == 0


def test_sessions_anchor_field_defaults_to_none(store):
    store.append("orgA", _ev(session_id="s1"))
    assert store.sessions("orgA")[0]["anchor"] == "none"


def test_sessions_anchor_field_reflects_batch_status(store):
    from teluvane import anchor_store, merkle

    for _ in range(2):
        store.append("orgA", _ev(session_id="s1"))
    head = store.events("orgA", "s1")[-1].hash
    root, proofs = merkle.build_tree([("orgA", "s1", head)])
    bid = anchor_store.insert_batch(store.pool, root, 43113, 1)
    anchor_store.insert_session_anchor(
        store.pool, "orgA", "s1", 2, bid, head, proofs[("orgA", "s1")]
    )
    anchor_store.mark_submitted(store.pool, bid, "0xtx")
    assert store.sessions("orgA")[0]["anchor"] == "submitted"


def test_concurrent_appends_to_one_session_keep_the_chain_intact(store):
    """Two threads appending to the same (org, session) at once must not fork the
    hash chain. Without the per-session advisory lock in append() both reads see the
    same prev_hash and verify_chain() then reports a legitimate session as tampered."""
    import threading

    from teluvane.store import Store

    barrier = threading.Barrier(8)
    errors = []

    def worker(n):
        try:
            barrier.wait()
            Store().append("orgA", _ev(session_id="race", intent=f"e{n}"))
        except Exception as exc:  # pragma: no cover - surfaced via errors list
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    evs = store.events("orgA", "race")
    assert len(evs) == 8
    assert len({e.seq for e in evs}) == 8
    assert store.verify_chain("orgA", "race") is True


def test_sessions_pagination(store):
    for i in range(5):
        store.append("orgA", _ev(session_id=f"s{i}"))
    page1 = store.sessions("orgA", limit=2, offset=0)
    page2 = store.sessions("orgA", limit=2, offset=2)
    assert len(page1) == 2 and len(page2) == 2
    assert {s["session_id"] for s in page1} != {s["session_id"] for s in page2}
