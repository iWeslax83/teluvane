# Erasable Event Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an organization erase the personal content of recorded events, on request or by a retention window, while every hash in the chain and every on-chain anchor keeps verifying.

**Architecture:** New events (hash version 2) put a salted commitment to `intent`, `args`, `output` and `approved_by` into the hash chain instead of the content. The content and its salt live in `event_payloads`; erasure deletes that row. Verification also re-checks each commitment while its payload exists, so tamper evidence does not weaken. An erasure log plus an `unexplained_erasures` counter make silent deletion visible. Old events (version 1) keep the frozen format and are reported as not erasable.

**Tech Stack:** Python 3.11, FastAPI, psycopg 3, Postgres, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-27-erasable-event-log-design.md`

## Global Constraints

- No em dashes (the long dash character) anywhere: code, comments, commit messages, docs, site text. Use a comma, period, colon, or parentheses.
- Copy: plain and concrete. Banned words: empower, unleash, revolutionize, supercharge and similar hype. Never write that TELUVANE "is GDPR compliant" or "makes you compliant". Write what the mechanism does, and that it is not legal advice.
- If a fact is not in the repo or this plan (a backup retention period, a legal citation, a date), stop and ask the maintainer. Do not guess.
- The v1 canonical form is frozen: `_event_canonical_v1` must produce byte-identical output to today's `_event_canonical`, or every stored chain breaks. `tests/test_store_canonical.py` and the shared vector `tests/fixtures/chain_vectors.json` guard it. Do not regenerate the v1 vector.
- Every SQL statement in `Store` must include an `org_id` predicate (`Store._assert_scoped` enforces it). Cross-org maintenance SQL (the retention job) lives outside `Store`, like `anchor.py`.
- Migrations are numbered, additive and idempotent (`IF NOT EXISTS`), and enable row level security on every new table, matching `migrations/0001` to `0013`.
- Python is 3.11, line length 100. New and changed Python must pass `ruff format` and `ruff check --select E,F,I` (older findings such as `tests/conftest.py` E402 are not yours).
- Commit messages use the repo's prefixes (`feat:`, `fix:`, `docs:`, `chore:`, `test:`). Never put claude.ai or session links in commits, PRs or comments.
- Every `pytest` run needs Postgres reachable (`tests/conftest.py` migrates once per session). See the ROADMAP setup section.
- Deploy order matters: run migration 0014 against production before starting the new API version (Task 8).

## Review Focus

- Editing an event's content in `event_payloads`, or its clear fields (`tool`, `ts`) in `events`, must make `verify_chain` fail. Tests: `test_verify_detects_payload_tampering`, `test_verify_detects_tampering_with_the_clear_fields`.
- Erasing must not change any canonical string or hash, or every anchored chain head would stop matching. Test: `test_erase_removes_content_but_chain_and_hashes_survive` compares `canonical_events` before and after.
- A payload row deleted outside the erase endpoint must show up as `unexplained_erasures`. Test: `test_silent_payload_deletion_is_reported_as_unexplained`.
- A session that mixes version 1 and version 2 events (every session in flight during deploy) must verify, and erasing it must erase the v2 part and report the v1 part. Tests: `test_v1_then_v2_in_one_session_verifies`, `test_erasing_after_v1_then_v2_events_keeps_the_chain`.
- A legal hold must block both manual erasure and the retention job; one client-supplied garbage `ts` in a legacy row must not break the retention job for every org; erasing in one org must not touch another. Tests: `test_legal_hold_blocks_erasure_and_retention`, `test_retention_job_erases_only_expired_payloads`, `test_erase_is_tenant_scoped`.
- `verify_chain` with no session id must check each session against its own genesis, not chain unrelated sessions together. Test: `test_verify_chain_across_sessions_is_per_session` (today's code reports any org with two sessions as tampered when called without `session_id`).

---

### Task 1: Migration, commitment helpers, event fields, test fixtures

**Files:**
- Create: `migrations/0014_erasable_payloads.sql`
- Create: `teluvane/commitments.py`
- Modify: `teluvane/schema.py` (`Event`)
- Modify: `tests/conftest.py`
- Test: `tests/test_commitments.py`

**Interfaces:**
- Produces: `commitments.payload_of(e: Event) -> dict`, `commitments.canonical_payload(payload: dict) -> str`, `commitments.new_salt() -> str` (64 hex chars), `commitments.commit(salt_hex: str, canonical: str) -> str`; `Event.hash_version: Optional[int]`, `Event.payload_commitment: Optional[str]`, `Event.erased: bool`; pytest fixtures `org` (creates `org1` and `org2`, returns `"org1"`) and `add_events(org_id, n=3, session="s1")`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_commitments.py`:

```python
from teluvane import commitments


def test_canonical_payload_is_compact_and_key_sorted():
    payload = {"output": "é", "intent": "x", "args": {"b": 1, "a": 2}, "approved_by": None}
    assert commitments.canonical_payload(payload) == (
        '{"approved_by":null,"args":{"a":2,"b":1},"intent":"x","output":"é"}'
    )


def test_commit_depends_on_salt_and_payload():
    salt = commitments.new_salt()
    assert len(salt) == 64 and salt != commitments.new_salt()
    a = commitments.commit(salt, "{}")
    assert a == commitments.commit(salt, "{}")
    assert a != commitments.commit(commitments.new_salt(), "{}")
    assert a != commitments.commit(salt, '{"a":1}')
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_commitments.py -v`
Expected: FAIL, `ImportError: cannot import name 'commitments'`.

- [ ] **Step 3: Create the helpers**

Create `teluvane/commitments.py`:

```python
# teluvane/teluvane/commitments.py
"""Salted payload commitments for hash version 2 events.

An event's personal content (intent, args, output, approved_by) is not hashed into the chain
directly. The chain hashes commit(salt, payload) instead. The salt is random per event and is
stored next to the payload, so deleting that row leaves a commitment nobody can brute-force
back into the content, while every chain hash stays valid."""

import hashlib
import json
import os

from .schema import Event


def payload_of(e: Event) -> dict:
    return {
        "intent": e.intent,
        "args": e.args,
        "output": e.output,
        "approved_by": e.approved_by,
    }


def canonical_payload(payload: dict) -> str:
    """Compact, key-sorted JSON. The exact string is stored, so verification never depends on
    a database round trip preserving number formatting or key order."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def new_salt() -> str:
    return os.urandom(32).hex()


def commit(salt_hex: str, canonical: str) -> str:
    return hashlib.sha256(bytes.fromhex(salt_hex) + canonical.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Add the event fields**

In `teluvane/schema.py`, in class `Event`, directly under the comment `# assigned on persist:` and above `seq`, add:

```python
    hash_version: Optional[int] = None  # 1 = plaintext in the hash, 2 = payload commitment
    payload_commitment: Optional[str] = None  # v2 only
    erased: bool = False  # v2 only: the payload was erased, the chain hash still verifies
```

- [ ] **Step 5: Create the migration**

Create `migrations/0014_erasable_payloads.sql`:

```sql
-- 0014: erasable event payloads (hash version 2).
-- v2 events hash a salted commitment to (intent, args, output, approved_by) instead of the
-- plaintext, and keep that plaintext in event_payloads. Deleting the payload row erases the
-- personal data while every hash in the chain, and every anchored chain head, stays valid.
-- v1 events (hash_version = 1) keep their plaintext in events and cannot be erased.
ALTER TABLE events ADD COLUMN IF NOT EXISTS hash_version SMALLINT NOT NULL DEFAULT 1;
ALTER TABLE events ADD COLUMN IF NOT EXISTS payload_commitment TEXT;

CREATE TABLE IF NOT EXISTS event_payloads (
    seq     BIGINT PRIMARY KEY REFERENCES events(seq) ON DELETE CASCADE,
    org_id  TEXT NOT NULL,
    salt    TEXT NOT NULL,   -- 32 random bytes, hex. Deleted with the payload.
    payload TEXT NOT NULL    -- the exact canonical JSON string that was committed to
);
CREATE INDEX IF NOT EXISTS idx_event_payloads_org ON event_payloads (org_id);
ALTER TABLE event_payloads ENABLE ROW LEVEL SECURITY;

-- Accountability record of every erasure. Holds seq numbers and a reason, never content.
CREATE TABLE IF NOT EXISTS erasure_log (
    id           BIGSERIAL PRIMARY KEY,
    org_id       TEXT NOT NULL,
    session_id   TEXT NOT NULL,
    seqs         JSONB NOT NULL,
    requested_by TEXT NOT NULL,
    reason       TEXT NOT NULL DEFAULT '',
    ts           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_erasure_log_org_session ON erasure_log (org_id, session_id);
ALTER TABLE erasure_log ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS org_retention (
    org_id         TEXT PRIMARY KEY REFERENCES orgs(id) ON DELETE CASCADE,
    retention_days INT CHECK (retention_days IS NULL OR retention_days >= 1),
    legal_hold     BOOLEAN NOT NULL DEFAULT false,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE org_retention ENABLE ROW LEVEL SECURITY;
```

- [ ] **Step 6: Update `tests/conftest.py`**

Add `from teluvane.schema import Event` under the existing `from teluvane.migrate import apply_migrations` import. In the `store` fixture, replace the TRUNCATE statement so it also clears the new tables:

```python
        cur.execute(
            "TRUNCATE events, verdicts, api_keys, org_members, orgs, "
            "anchor_batches, session_anchors, session_anchor_public, erasure_log, org_retention "
            "RESTART IDENTITY CASCADE"
        )
```

Append these two fixtures at the end of the file:

```python
@pytest.fixture
def org(store):
    """Two orgs exist (org1, org2) so tenant-isolation tests can use both; returns "org1"."""
    with store.pool.connection() as conn, conn.cursor() as cur:
        for oid in ("org1", "org2"):
            cur.execute(
                "INSERT INTO orgs(id,name,owner_user_id) VALUES(%s,'o','u') ON CONFLICT DO NOTHING",
                (oid,),
            )
        conn.commit()
    return "org1"


@pytest.fixture
def add_events(store):
    """add_events(org_id, n=3, session="s1") appends n tool_call events that carry personal data."""

    def _add(org_id, n=3, session="s1"):
        return [
            store.append(
                org_id,
                Event(
                    agent_id="a",
                    session_id=session,
                    kind="tool_call",
                    tool="t",
                    intent=f"email jane@example.com step {i}",
                    args={"ssn": "078-05-1120"},
                    output="done",
                    approved_by="human:u1",
                ),
            )
            for i in range(n)
        ]

    return _add
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_commitments.py -v` then the whole suite `pytest -q`.
Expected: PASS. The suite is unchanged in behavior; `apply_migrations()` applied `0014` on the test database.

- [ ] **Step 8: Format, lint, commit**

```bash
ruff format teluvane/commitments.py teluvane/schema.py tests/test_commitments.py tests/conftest.py
ruff check --select E,F,I teluvane/commitments.py tests/test_commitments.py
git add migrations/0014_erasable_payloads.sql teluvane/commitments.py teluvane/schema.py tests/conftest.py tests/test_commitments.py
git commit -m "feat: migration and helpers for erasable event payloads"
```

---

### Task 2: Write, read and verify version 2 events

**Files:**
- Modify: `teluvane/store.py`
- Test: `tests/test_event_commitments.py`

**Interfaces:**
- Consumes: `commitments.*` and the `org`/`add_events` fixtures from Task 1.
- Produces: `Store.append` writes v2 by default (v1 when env `TELUVANE_EVENT_HASH_VERSION=1`); `Store.events(org_id, session_id=None) -> list[Event]` hydrates v2 payloads and sets `erased=True` when a v2 payload row is missing; `Store._events_with_salt(org_id, session_id=None) -> list[tuple[Event, str | None]]`; `Store.verify_chain(org_id, session_id=None) -> bool` (per-session, also checks commitments); `Store.payload_openings(org_id, session_id) -> list[{"seq", "salt", "payload"}]`; module functions `_event_canonical_v1`, `_event_canonical_v2`, `_event_canonical`, `_event_digest`, `_write_version`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_event_commitments.py`:

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_event_commitments.py -v`
Expected: FAIL (`assert None == 2`: events are still written as version 1).

- [ ] **Step 3: Edit `teluvane/store.py`**

3a. Imports: add `import os` after `import json`, and `from . import commitments` above `from .cost import compute_cost`.

3b. Replace the existing `_event_canonical` and `_event_digest` functions (they sit above `class Store`) with these five:

```python
def _event_canonical_v1(prev_hash: str, e: Event) -> str:
    # The exact string the v1 hash chain digests. org_id is included so an event is
    # cryptographically bound to its tenant. Output bytes are frozen: changing
    # this invalidates every stored v1 chain.
    return json.dumps(
        {
            "prev": prev_hash,
            "org_id": e.org_id,
            "agent_id": e.agent_id,
            "session_id": e.session_id,
            "kind": e.kind,
            "intent": e.intent,
            "tool": e.tool,
            "args": e.args,
            "output": e.output,
            "approved_by": e.approved_by,
            "ts": e.ts,
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _event_canonical_v2(prev_hash: str, e: Event) -> str:
    # v2 digests a salted commitment to the personal content instead of the content itself,
    # so the content can be erased later without breaking any hash. Frozen like v1.
    return json.dumps(
        {
            "v": 2,
            "prev": prev_hash,
            "org_id": e.org_id,
            "agent_id": e.agent_id,
            "session_id": e.session_id,
            "kind": e.kind,
            "tool": e.tool,
            "ts": e.ts,
            "payload_commitment": e.payload_commitment,
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _event_canonical(prev_hash: str, e: Event) -> str:
    return (_event_canonical_v2 if e.hash_version == 2 else _event_canonical_v1)(prev_hash, e)


def _event_digest(prev_hash: str, e: Event) -> str:
    return hashlib.sha256(_event_canonical(prev_hash, e).encode("utf-8")).hexdigest()


def _write_version() -> int:
    """Hash version for new events. TELUVANE_EVENT_HASH_VERSION=1 is the rollback switch."""
    return 1 if os.environ.get("TELUVANE_EVENT_HASH_VERSION") == "1" else 2
```

3c. Replace `Store.append` with:

```python
    def append(self, org_id: str, e: Event) -> Event:
        sql_last = (
            "SELECT hash FROM events WHERE org_id=%s AND session_id=%s ORDER BY seq DESC LIMIT 1"
        )
        sql_ins = (
            "INSERT INTO events"
            "(org_id,agent_id,session_id,kind,intent,tool,args,output,approved_by,ts,"
            "prev_hash,hash,model,input_tokens,output_tokens,cost_usd,hash_version,"
            "payload_commitment)"
            " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING seq"
        )
        sql_payload = "INSERT INTO event_payloads(seq,org_id,salt,payload) VALUES(%s,%s,%s,%s)"
        self._assert_scoped(org_id, sql_last)
        self._assert_scoped(org_id, sql_ins)
        self._assert_scoped(org_id, sql_payload)
        e.org_id = org_id
        # cost_usd isn't part of the hash chain (see _event_digest), so it's safe to fill it
        # in here from a known model's pricing when the caller supplied tokens but no cost.
        if e.cost_usd is None:
            e.cost_usd = compute_cost(e.model, e.input_tokens, e.output_tokens)
        e.hash_version = _write_version()
        salt = payload = None
        if e.hash_version == 2:
            salt = commitments.new_salt()
            payload = commitments.canonical_payload(commitments.payload_of(e))
            e.payload_commitment = commitments.commit(salt, payload)
        # v2 keeps the personal content only in event_payloads; the events row carries blanks.
        if e.hash_version == 2:
            row_intent, row_args, row_output, row_approved = "", {}, "", None
        else:
            row_intent, row_args, row_output, row_approved = (
                e.intent,
                e.args,
                e.output,
                e.approved_by,
            )
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # Serialize appends to the same (org, session) for the life of this
                # transaction. Without it two concurrent appends both read the same
                # prev_hash, both digest from it, and the hash chain forks: verify_chain
                # then walks by seq and reports a perfectly legitimate session as
                # TAMPERED. The "append:" prefix keeps this key distinct from the
                # auditlock key for the same session, so an in-flight audit (which can
                # hold its lock across a slow tribunal run) never blocks ingest.
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"append:{org_id}:{e.session_id}",),
                )
                cur.execute(sql_last, (org_id, e.session_id))
                row = cur.fetchone()
                e.prev_hash = row["hash"] if row else "GENESIS"
                e.hash = _event_digest(e.prev_hash, e)
                cur.execute(
                    sql_ins,
                    (
                        org_id,
                        e.agent_id,
                        e.session_id,
                        e.kind,
                        row_intent,
                        e.tool,
                        json.dumps(row_args, ensure_ascii=False),
                        row_output,
                        row_approved,
                        e.ts,
                        e.prev_hash,
                        e.hash,
                        e.model,
                        e.input_tokens,
                        e.output_tokens,
                        e.cost_usd,
                        e.hash_version,
                        e.payload_commitment,
                    ),
                )
                e.seq = cur.fetchone()["seq"]
                if e.hash_version == 2:
                    cur.execute(sql_payload, (e.seq, org_id, salt, payload))
            conn.commit()
        return e
```

3d. Replace `Store.events` with these two methods:

```python
    def _events_with_salt(
        self, org_id: str, session_id: Optional[str] = None
    ) -> list[tuple[Event, Optional[str]]]:
        """Events in seq order, v2 payloads hydrated from event_payloads. The salt is returned
        beside the event (None for v1 or erased events) for commitment checks."""
        sql = (
            "SELECT e.*, p.payload AS _payload, p.salt AS _salt FROM events e "
            "LEFT JOIN event_payloads p ON p.seq = e.seq AND p.org_id = e.org_id "
            "WHERE e.org_id=%s"
        )
        params: tuple = (org_id,)
        if session_id:
            sql += " AND e.session_id=%s"
            params += (session_id,)
        sql += " ORDER BY e.seq ASC"
        self._assert_scoped(org_id, sql)
        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        out: list[tuple[Event, Optional[str]]] = []
        for r in rows:
            payload, salt = r.pop("_payload"), r.pop("_salt")
            if r["hash_version"] == 2:
                if payload is None:
                    r["erased"] = True
                else:
                    r.update(json.loads(payload))
            out.append((Event(**r), salt))
        return out

    def events(self, org_id: str, session_id: Optional[str] = None) -> list[Event]:
        return [e for e, _ in self._events_with_salt(org_id, session_id)]
```

3e. Replace `Store.verify_chain` with:

```python
    def verify_chain(self, org_id: str, session_id: Optional[str] = None) -> bool:
        """Every event's hash must match its canonical form and link to the previous event in
        its own session. For v2 events whose payload still exists, the payload must also match
        its commitment; without that check editing event_payloads would go unnoticed."""
        prev_by_session: dict[str, str] = {}
        for e, salt in self._events_with_salt(org_id, session_id):
            prev = prev_by_session.get(e.session_id, "GENESIS")
            if _event_digest(prev, e) != e.hash:
                return False
            if e.hash_version == 2 and salt is not None:
                canonical = commitments.canonical_payload(commitments.payload_of(e))
                if commitments.commit(salt, canonical) != e.payload_commitment:
                    return False
            prev_by_session[e.session_id] = e.hash
        return True
```

3f. Add `payload_openings` after `verify_chain`. It returns the salt and canonical payload of every v2 event whose payload still exists, so an auditor can recompute each commitment:

```python
    def payload_openings(self, org_id: str, session_id: str) -> list[dict]:
        """Salt and canonical payload for every v2 event whose payload still exists, so an
        auditor can recompute each commitment: sha256(bytes.fromhex(salt) + payload_utf8)."""
        sql = (
            "SELECT p.seq, p.salt, p.payload FROM event_payloads p "
            "JOIN events e ON e.seq = p.seq "
            "WHERE p.org_id=%s AND e.session_id=%s ORDER BY p.seq"
        )
        self._assert_scoped(org_id, sql)
        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (org_id, session_id))
            return [dict(r) for r in cur.fetchall()]
```

Leave `canonical_events` untouched: it already calls `_event_canonical`, which now dispatches on the event's version.

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_event_commitments.py tests/test_store_canonical.py tests/test_store.py -v` then `pytest -q`.
Expected: PASS, and the earlier suite still green (the v1 vector test proves the frozen format did not move).

- [ ] **Step 5: Format, lint, commit**

```bash
ruff format teluvane/store.py tests/test_event_commitments.py
ruff check --select E,F,I teluvane/store.py tests/test_event_commitments.py
git add teluvane/store.py tests/test_event_commitments.py
git commit -m "feat: hash a salted commitment to event content (hash version 2)"
```

---

### Task 3: Erase and report

**Files:**
- Modify: `teluvane/store.py`
- Test: `tests/test_erasure.py`

**Interfaces:**
- Consumes: Task 2.
- Produces: `REDACTED_RATIONALE: str`; `Store.erase_payloads(org_id, session_id, requested_by, reason="", seqs=None) -> {"erased": int, "already_erased": int, "legacy_unerasable": int}`; `Store.verify_report(org_id, session_id) -> {"chain_intact": bool, "erased_events": int, "unexplained_erasures": int}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_erasure.py`:

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_erasure.py -v`
Expected: FAIL, `AttributeError: 'Store' object has no attribute 'erase_payloads'`.

- [ ] **Step 3: Add the methods to `teluvane/store.py`**

Add this module-level constant directly above `class Store`:

```python
REDACTED_RATIONALE = "[redacted: the source data for this finding was erased]"
```

Add these two methods to `Store`, after `payload_openings` and before `canonical_events`:

```python
    def verify_report(self, org_id: str, session_id: str) -> dict:
        """verify_chain plus erasure accounting. `unexplained_erasures` counts v2 events whose
        payload is missing but that no erasure_log entry covers: either a deletion that did not
        go through erase_payloads, or tampering. The log is not itself tamper-evident yet."""
        events = self.events(org_id, session_id)
        erased = {e.seq for e in events if e.erased}
        sql = "SELECT seqs FROM erasure_log WHERE org_id=%s AND session_id=%s"
        self._assert_scoped(org_id, sql)
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (org_id, session_id))
            logged = {int(q) for (seqs,) in cur.fetchall() for q in seqs}
        return {
            "chain_intact": self.verify_chain(org_id, session_id),
            "erased_events": len(erased),
            "unexplained_erasures": len(erased - logged),
        }

    def erase_payloads(
        self,
        org_id: str,
        session_id: str,
        requested_by: str,
        reason: str = "",
        seqs: Optional[list[int]] = None,
    ) -> dict:
        """Erase the personal content of v2 events in a session (all of them, or just `seqs`).
        Chain hashes and anchors stay valid. Also redacts the session's verdict rationales,
        which quote the log. v1 events cannot be erased: their plaintext is inside the hash."""
        sql_scope = (
            "SELECT e.seq, e.hash_version, (p.seq IS NOT NULL) AS has_payload FROM events e "
            "LEFT JOIN event_payloads p ON p.seq = e.seq AND p.org_id = e.org_id "
            "WHERE e.org_id=%s AND e.session_id=%s"
        )
        params: tuple = (org_id, session_id)
        if seqs is not None:
            sql_scope += " AND e.seq = ANY(%s)"
            params += (seqs,)
        sql_del = "DELETE FROM event_payloads WHERE org_id=%s AND seq = ANY(%s)"
        sql_log = (
            "INSERT INTO erasure_log(org_id,session_id,seqs,requested_by,reason) "
            "VALUES(%s,%s,%s,%s,%s)"
        )
        sql_redact = "UPDATE verdicts SET rationale=%s WHERE org_id=%s AND session_id=%s"
        for q in (sql_scope, sql_del, sql_log, sql_redact):
            self._assert_scoped(org_id, q)
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql_scope, params)
                scope = cur.fetchall()
                erasable = [r["seq"] for r in scope if r["hash_version"] == 2 and r["has_payload"]]
                result = {
                    "erased": len(erasable),
                    "already_erased": sum(
                        1 for r in scope if r["hash_version"] == 2 and not r["has_payload"]
                    ),
                    "legacy_unerasable": sum(1 for r in scope if r["hash_version"] != 2),
                }
                if erasable:
                    cur.execute(sql_del, (org_id, erasable))
                    cur.execute(
                        sql_log, (org_id, session_id, json.dumps(erasable), requested_by, reason)
                    )
                    cur.execute(sql_redact, (REDACTED_RATIONALE, org_id, session_id))
            conn.commit()
        return result
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_erasure.py tests/test_event_commitments.py -v` then `pytest -q`.
Expected: PASS.

- [ ] **Step 5: Format, lint, commit**

```bash
ruff format teluvane/store.py tests/test_erasure.py
ruff check --select E,F,I teluvane/store.py tests/test_erasure.py
git add teluvane/store.py tests/test_erasure.py
git commit -m "feat: erase event payloads while keeping the chain and anchors valid"
```

---

### Task 4: API, retention, and scheduler

**Files:**
- Create: `teluvane/retention.py`, `teluvane/routes/privacy.py`
- Modify: `teluvane/routes/sessions.py`, `teluvane/scheduler.py`, `teluvane/ingest.py`
- Test: `tests/test_privacy_api.py`

**Interfaces:**
- Consumes: `Store.erase_payloads`, `Store.verify_report` from Task 3; `require_owner` from `teluvane/orgs.py`.
- Produces: `POST /sessions/{session_id}/erase` (owner only; body `{"seqs": [int] | null, "reason": str}`; 404 unknown session, 409 legal hold or only legacy events); `GET /orgs/retention` (any member); `PUT /orgs/retention` (owner; body `{"retention_days": int | null (1..3650), "legal_hold": bool}`); `GET /verify?session_id=` now returns the `verify_report` dict; `POST /events` returns 422 for a non-ISO-8601 `ts`; `retention.get_retention`, `retention.set_retention`, `retention.run_retention(pool=None) -> int`; `scheduler.run_retention_cycle() -> int`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_privacy_api.py`:

```python
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from teluvane.apikeys import create_api_key
from teluvane.db import get_pool
from teluvane.orgs import create_org
from teluvane.retention import get_retention, run_retention, set_retention


def _jwt(user_id):
    now = int(time.time())
    return jwt.encode(
        {"sub": user_id, "aud": "authenticated", "iat": now, "exp": now + 3600},
        "test-secret",
        algorithm="HS256",
    )


@pytest.fixture
def client(store):
    from teluvane.ingest import app

    return TestClient(app)


@pytest.fixture
def seeded(client, store):
    org = create_org("Acme", "owner1")
    key = create_api_key(org, "ci")
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO org_members(org_id,user_id,role) VALUES(%s,'member1','member')", (org,)
        )
        conn.commit()
    for i in range(2):
        r = client.post(
            "/events",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "agent_id": "a",
                "session_id": "sx",
                "kind": "llm_call",
                "intent": f"call jane@example.com {i}",
            },
        )
        assert r.status_code == 200
    return org, {"Authorization": f"Bearer {_jwt('owner1')}"}


def test_owner_can_erase_and_verify_still_passes(client, seeded):
    org, h = seeded
    r = client.post("/sessions/sx/erase", json={"reason": "art 17"}, headers=h)
    assert r.status_code == 200 and r.json()["erased"] == 2
    v = client.get("/verify?session_id=sx", headers=h).json()
    assert v == {"chain_intact": True, "erased_events": 2, "unexplained_erasures": 0}
    ev = client.get("/events?session_id=sx", headers=h).json()
    assert all(e["erased"] and e["intent"] == "" for e in ev)


def test_erase_without_body_erases_everything(client, seeded):
    _, h = seeded
    assert client.post("/sessions/sx/erase", headers=h).json()["erased"] == 2


def test_member_cannot_erase(client, seeded):
    _, _ = seeded
    r = client.post("/sessions/sx/erase", headers={"Authorization": f"Bearer {_jwt('member1')}"})
    assert r.status_code == 403


def test_unknown_session_404(client, seeded):
    _, h = seeded
    assert client.post("/sessions/nope/erase", headers=h).status_code == 404


def test_legal_hold_blocks_erasure_and_retention(client, seeded):
    org, h = seeded
    assert (
        client.put(
            "/orgs/retention", json={"retention_days": 1, "legal_hold": True}, headers=h
        ).status_code
        == 200
    )
    assert client.post("/sessions/sx/erase", headers=h).status_code == 409
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE events SET ts='2020-01-01T00:00:00+00:00' WHERE org_id=%s", (org,))
        conn.commit()
    assert run_retention() == 0
    assert (
        client.put(
            "/orgs/retention", json={"retention_days": 1, "legal_hold": False}, headers=h
        ).status_code
        == 200
    )
    assert client.post("/sessions/sx/erase", headers=h).status_code == 200


def test_retention_validation_and_member_read_only(client, seeded):
    _, h = seeded
    assert client.put("/orgs/retention", json={"retention_days": 0}, headers=h).status_code == 422
    m = {"Authorization": f"Bearer {_jwt('member1')}"}
    assert client.put("/orgs/retention", json={"retention_days": 30}, headers=m).status_code == 403
    assert client.get("/orgs/retention", headers=m).json() == {
        "retention_days": None,
        "legal_hold": False,
    }


def test_retention_job_erases_only_expired_payloads(client, seeded):
    org, h = seeded
    set_retention(org, 30, False)
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE events SET ts='2020-01-01T00:00:00+00:00' "
            "WHERE seq=(SELECT min(seq) FROM events WHERE org_id=%s)",
            (org,),
        )
        cur.execute(
            "UPDATE events SET ts='not a timestamp' "
            "WHERE seq=(SELECT max(seq) FROM events WHERE org_id=%s)",
            (org,),
        )
        conn.commit()
    assert run_retention() == 1
    assert run_retention() == 0
    ev = client.get("/events?session_id=sx", headers=h).json()
    assert [e["erased"] for e in ev] == [True, False]
    assert get_retention(org)["retention_days"] == 30


def test_ingest_rejects_unparseable_timestamp(client, seeded):
    org, _ = seeded
    key = create_api_key(org, "ci2")
    r = client.post(
        "/events",
        headers={"Authorization": f"Bearer {key}"},
        json={"agent_id": "a", "session_id": "sx", "kind": "llm_call", "ts": "yesterday"},
    )
    assert r.status_code == 422
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_privacy_api.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'teluvane.retention'`.

- [ ] **Step 3: Create the retention module**

Create `teluvane/retention.py`:

```python
# teluvane/teluvane/retention.py
"""Per-org retention window and legal hold for event payloads (GDPR storage limitation).

A retention job erases the payload of v2 events older than the org's retention_days, exactly
like a manual erasure: chain hashes and anchors stay valid, an erasure_log row records it. A
legal hold suspends both the job and manual erasure for that org."""

from .db import get_pool
from .store import REDACTED_RATIONALE

MAX_RETENTION_DAYS = 3650


def get_retention(org_id: str) -> dict:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT retention_days, legal_hold FROM org_retention WHERE org_id=%s", (org_id,)
        )
        row = cur.fetchone()
    return (
        {"retention_days": row[0], "legal_hold": row[1]}
        if row
        else {
            "retention_days": None,
            "legal_hold": False,
        }
    )


def set_retention(org_id: str, retention_days: int | None, legal_hold: bool) -> None:
    if retention_days is not None and not 1 <= retention_days <= MAX_RETENTION_DAYS:
        raise ValueError(f"retention_days must be between 1 and {MAX_RETENTION_DAYS}")
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO org_retention(org_id,retention_days,legal_hold) VALUES(%s,%s,%s) "
            "ON CONFLICT (org_id) DO UPDATE SET retention_days=EXCLUDED.retention_days, "
            "legal_hold=EXCLUDED.legal_hold, updated_at=now()",
            (org_id, retention_days, legal_hold),
        )
        conn.commit()


# The CASE guards the cast: ts is client-supplied text, and one malformed legacy row must not
# make this job fail for every org. Rows that do not parse are simply never expired.
_RETENTION_SQL = """
WITH doomed AS (
    SELECT p.seq, p.org_id, e.session_id
    FROM event_payloads p
    JOIN events e ON e.seq = p.seq
    JOIN org_retention r ON r.org_id = p.org_id
    WHERE r.retention_days IS NOT NULL AND NOT r.legal_hold
      AND CASE WHEN e.ts ~ '^\\d{4}-\\d{2}-\\d{2}T[0-9:.]+(Z|[+-]\\d{2}:\\d{2})$'
               THEN e.ts::timestamptz END < now() - make_interval(days => r.retention_days)
), gone AS (
    DELETE FROM event_payloads p USING doomed d WHERE p.seq = d.seq
    RETURNING d.org_id, d.session_id, d.seq
)
INSERT INTO erasure_log(org_id, session_id, seqs, requested_by, reason)
SELECT org_id, session_id, jsonb_agg(seq ORDER BY seq), 'system:retention', 'retention policy'
FROM gone GROUP BY org_id, session_id
RETURNING org_id, session_id, jsonb_array_length(seqs)
"""


def run_retention(pool=None) -> int:
    """Erase expired payloads for every org with a retention window and no legal hold.
    Idempotent and safe to run on several instances at once. Returns payloads erased."""
    pool = pool or get_pool()
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(_RETENTION_SQL)
        touched = cur.fetchall()
        for org_id, session_id, _ in touched:
            cur.execute(
                "UPDATE verdicts SET rationale=%s WHERE org_id=%s AND session_id=%s",
                (REDACTED_RATIONALE, org_id, session_id),
            )
        conn.commit()
    return sum(n for _, _, n in touched)
```

The `CASE` around the `ts` cast is deliberate: `ts` is client-supplied text, and one unparseable legacy value must not make the job fail for every org.

- [ ] **Step 4: Create the routes**

Create `teluvane/routes/privacy.py`:

```python
# teluvane/teluvane/routes/privacy.py
"""GDPR controls: erase a session's event payloads, set a retention window, place a legal hold."""

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..appstate import store
from ..auth import current_org, verify_jwt
from ..orgs import require_owner
from ..retention import MAX_RETENTION_DAYS, get_retention, set_retention

router = APIRouter()


class EraseRequest(BaseModel):
    seqs: list[int] | None = None  # None erases every erasable event in the session
    reason: str = Field(default="", max_length=500)


def _owner_id(org_id: str, authorization: str | None) -> str:
    user_id = verify_jwt(authorization[len("Bearer ") :])
    require_owner(org_id, user_id)
    return user_id


@router.post("/sessions/{session_id}/erase")
def erase_session(
    session_id: str,
    body: EraseRequest = Body(default_factory=EraseRequest),
    org_id: str = Depends(current_org),
    authorization: str = Header(default=None),
) -> dict:
    user_id = _owner_id(org_id, authorization)
    if get_retention(org_id)["legal_hold"]:
        raise HTTPException(status_code=409, detail="erasure is blocked while a legal hold is on")
    if not store.events(org_id, session_id):
        raise HTTPException(status_code=404, detail="session not found")
    result = store.erase_payloads(
        org_id, session_id, requested_by=user_id, reason=body.reason, seqs=body.seqs
    )
    if result["erased"] == 0 and result["legacy_unerasable"] > 0:
        raise HTTPException(
            status_code=409,
            detail="these events predate erasable payloads (hash version 1) and cannot be erased",
        )
    return result


@router.get("/orgs/retention")
def read_retention(org_id: str = Depends(current_org)) -> dict:
    return get_retention(org_id)


@router.put("/orgs/retention")
def write_retention(
    retention_days: int | None = Body(default=None, ge=1, le=MAX_RETENTION_DAYS),
    legal_hold: bool = Body(default=False),
    org_id: str = Depends(current_org),
    authorization: str = Header(default=None),
) -> dict:
    _owner_id(org_id, authorization)
    set_retention(org_id, retention_days, legal_hold)
    return get_retention(org_id)
```

- [ ] **Step 5: Wire it in**

5a. `teluvane/routes/sessions.py`: add `from datetime import datetime` under `import os`, add `HTTPException` to the `from fastapi import ...` line, then replace the `ingest` and `verify` handlers with:

```python
@router.post("/events")
@limiter.limit(lambda: os.environ.get("EVENTS_RATE_LIMIT", "120/minute"))
def ingest(request: Request, e: Event, org_id: str = Depends(org_from_api_key)) -> Event:
    # ts is client supplied and later cast to timestamptz by the stats and retention
    # queries; one unparseable value would break those for the whole org. Checked here, not
    # in the Event model, so a legacy row with a bad ts can still be read back.
    try:
        datetime.fromisoformat(e.ts)
    except ValueError:
        raise HTTPException(status_code=422, detail="ts must be an ISO 8601 timestamp")
    return store.append(org_id, e)


@router.get("/verify")
def verify(session_id: str | None = None, org_id: str = Depends(current_org)) -> dict:
    if session_id:
        return store.verify_report(org_id, session_id)
    return {"chain_intact": store.verify_chain(org_id)}
```

The timestamp check lives here and not in the `Event` model on purpose: the model is also used to read stored rows back, and a legacy row with a bad `ts` must stay readable.

5b. `teluvane/scheduler.py`: add `from .retention import run_retention` under `from .orgs import get_policy_framework`; add these two globals under `_last_anchor_run = None`:

```python
_last_retention_run = None
RETENTION_INTERVAL_MINUTES = 60
```

and add this function above `get_schedule`:

```python
def run_retention_cycle() -> int:
    """Erase expired event payloads, at most once per RETENTION_INTERVAL_MINUTES per process."""
    global _last_retention_run
    now = datetime.now(timezone.utc)
    if (
        _last_retention_run is not None
        and (now - _last_retention_run).total_seconds() < RETENTION_INTERVAL_MINUTES * 60
    ):
        return 0
    _last_retention_run = now
    return run_retention(get_pool())
```

5c. `teluvane/ingest.py`: add `privacy` to the routes import, so it reads `from .routes import anchor, billing, evidence, orgs, policy, privacy, sessions`; replace the scheduler import with:

```python
from .scheduler import (
    TICK_INTERVAL_SECONDS,
    run_anchor_cycle,
    run_due_schedules,
    run_retention_cycle,
)
```

replace `_scheduler_loop` with:

```python
def _scheduler_loop() -> None:
    while not _scheduler_stop.wait(TICK_INTERVAL_SECONDS):
        try:
            run_due_schedules(
                store,
                FRAMEWORK_PACKS,
                hosted_api_key=os.environ.get("TELUVANE_HOSTED_ANTHROPIC_KEY"),
            )
        except Exception:
            logging.exception("scheduled tribunal tick failed")
        try:
            run_anchor_cycle()
        except Exception:
            logging.exception("anchor tick failed")
        try:
            run_retention_cycle()
        except Exception:
            logging.exception("retention tick failed")
```

and add `app.include_router(privacy.router)` after `app.include_router(billing.router)`.

- [ ] **Step 6: Run the tests**

Run: `pytest tests/test_privacy_api.py -v` then `pytest -q`.
Expected: PASS.

- [ ] **Step 7: Format, lint, commit**

```bash
ruff format teluvane/retention.py teluvane/routes teluvane/scheduler.py teluvane/ingest.py tests/test_privacy_api.py
ruff check --select E,F,I teluvane/retention.py teluvane/routes/privacy.py tests/test_privacy_api.py
git add teluvane tests/test_privacy_api.py
git commit -m "feat: erase, retention and legal hold endpoints with an hourly retention job"
```

---

### Task 5: Evidence packs and the tribunal understand erased events

**Files:**
- Modify: `teluvane/evidence.py`, `teluvane/routes/evidence.py`, `teluvane/tribunal.py`
- Test: append to `tests/test_privacy_api.py`; create `tests/test_tribunal_erased.py`

**Interfaces:**
- Consumes: `Store.verify_report`, `Store.payload_openings` (Task 3), `Event.erased` (Task 1), the Plan 2 `tribunal.py` (this plan assumes Plan 2 is merged; if it is not, apply the same one-line change to the current `_events_to_text`).
- Produces: `build_evidence_pack(..., erasure: dict | None = None, openings: list[dict] | None = None)` (same for `build_evidence_pdf`); evidence JSON gains `openings` and summary fields `erased_events`, `unexplained_erasures`; the HTML shows `[erased]` and an erasure notice.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_privacy_api.py`:

```python
def test_evidence_pack_states_erasure_and_still_verifies(client, seeded):
    _, h = seeded
    client.post("/sessions/sx/erase", headers=h)
    html = client.get("/evidence/sx", headers=h).text
    assert "intact" in html and "Erased content" in html and "[erased]" in html
    assert "jane@example.com" not in html


def test_evidence_pack_before_erasure_lists_openings(client, seeded):
    org, h = seeded
    from teluvane.appstate import store
    from teluvane.evidence import build_evidence_pack

    events = store.events(org, "sx")
    pack = build_evidence_pack(
        "sx", events, [], "EU AI Act", True, openings=store.payload_openings(org, "sx")
    )
    assert len(pack["json"]["openings"]) == 2
```

Create `tests/test_tribunal_erased.py`:

```python
from teluvane.schema import Event
from teluvane.tribunal import _events_to_text


def test_erased_events_are_marked_not_shown():
    e = Event(
        agent_id="a", session_id="s", kind="tool_call", tool="t", intent="secret words", erased=True
    )
    e.seq = 4
    text = _events_to_text([e])
    assert "[payload erased]" in text and "secret words" not in text
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_privacy_api.py tests/test_tribunal_erased.py -v`
Expected: FAIL (`TypeError: build_evidence_pack() got an unexpected keyword argument 'openings'`, and `[payload erased]` missing).

- [ ] **Step 3: Edit `teluvane/evidence.py`**

Replace `build_evidence_pack`, `build_evidence_pdf` and `_render_html` with the versions below, and add `_render_erasure_html` next to `_render_anchor_html`:

```python
def build_evidence_pack(
    session_id: str,
    events: list[Event],
    verdicts: list[Verdict],
    framework: str,
    chain_intact: bool,
    anchor: dict | None = None,
    canonical: list[dict] | None = None,
    erasure: dict | None = None,
    openings: list[dict] | None = None,
) -> dict:
    violations = [v for v in verdicts if v.violation]
    summary = {
        "events": len(events),
        "violations": len(violations),
        "chain_intact": chain_intact,
        "highest_severity": _highest_sev(violations),
        "erased_events": (erasure or {}).get("erased_events", 0),
        "unexplained_erasures": (erasure or {}).get("unexplained_erasures", 0),
    }
    js = {
        "session_id": session_id,
        "framework": framework,
        "summary": summary,
        "anchor": anchor,
        "canonical": canonical,
        # v2 payload openings: sha256(bytes.fromhex(salt) + payload.encode()) must equal the
        # event's payload_commitment. Erased events have no opening.
        "openings": openings,
        "violations": [v.model_dump() for v in violations],
        "events": [e.model_dump() for e in events],
    }
    return {
        "json": js,
        "html": _render_html(session_id, framework, summary, violations, events, anchor),
    }


def build_evidence_pdf(
    session_id: str,
    events: list[Event],
    verdicts: list[Verdict],
    framework: str,
    chain_intact: bool,
    anchor: dict | None = None,
    canonical: list[dict] | None = None,
    erasure: dict | None = None,
    openings: list[dict] | None = None,
) -> bytes:
    # Imported lazily: weasyprint pulls in cairo/pango bindings that only the PDF export
    # path needs, so the rest of the API can boot even if that native stack is unavailable.
    from weasyprint import HTML

    pack = build_evidence_pack(
        session_id, events, verdicts, framework, chain_intact, anchor, canonical, erasure, openings
    )
    return HTML(string=pack["html"]).write_pdf()


def _render_erasure_html(summary: dict) -> str:
    erased, unexplained = summary["erased_events"], summary["unexplained_erasures"]
    if not erased:
        return ""
    note = (
        f"<p><b>Erased content:</b> the personal content of {erased} event(s) was erased "
        "on request or by retention policy. Their hashes stay in the chain, so the chain "
        "still verifies, but the erased content can no longer be shown.</p>"
    )
    if unexplained:
        note += (
            f"<p><b>Warning:</b> {unexplained} of those erasures have no entry in the "
            "erasure log. Treat the session as suspect until they are explained.</p>"
        )
    return note


def _render_html(session_id, framework, summary, violations, events, anchor=None) -> str:
    rows = "".join(
        f"<tr><td>{_html.escape(v.rule_id)}</td><td>{v.severity}</td>"
        f"<td>{v.confidence:.2f}</td><td>{_html.escape(str(v.evidence_seqs))}</td>"
        f"<td>{_html.escape(v.framework_ref)}</td><td>{_html.escape(v.rationale)}</td></tr>"
        for v in violations
    )
    ev_rows = "".join(
        f"<tr><td>#{e.seq}</td><td>{e.kind}</td><td>{_html.escape(e.tool or '')}</td>"
        f"<td>{_html.escape('[erased]' if e.erased else e.intent)}</td>"
        f"<td><code>{_html.escape('[erased]' if e.erased else str(e.args))}</code></td></tr>"
        for e in events
    )
    chain = "&#9989; intact" if summary["chain_intact"] else "&#10060; TAMPERED"
    anchor_html = _render_anchor_html(anchor)
    erasure_html = _render_erasure_html(summary)
    return f"""<!doctype html><meta charset=utf-8>
<title>Evidence Pack: {_html.escape(session_id)}</title>
<style>body{{font-family:system-ui;margin:2rem;color:#1a1714}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
td,th{{border:1px solid #ccc;padding:6px;text-align:left;font-size:14px}}
h1{{color:#b4451f}}.sev-critical{{color:#b4451f;font-weight:700}}</style>
<h1>Compliance Evidence Pack</h1>
<p><b>Framework:</b> {_html.escape(framework)} &nbsp;|&nbsp;
<b>Session:</b> {_html.escape(session_id)} &nbsp;|&nbsp;
<b>Tamper-evidence chain:</b> {chain}</p>
<p><b>Events:</b> {summary["events"]} &nbsp;|&nbsp;
<b>Violations:</b> {summary["violations"]} &nbsp;|&nbsp;
<b>Highest severity:</b> {summary["highest_severity"]}</p>
{erasure_html}
{anchor_html}
<h2>Violations</h2><table><tr><th>Rule</th><th>Severity</th><th>Confidence</th>
<th>Evidence</th><th>Framework ref</th><th>Rationale</th></tr>{rows}</table>
<h2>Full Action Log</h2><table><tr><th>#</th><th>Kind</th><th>Tool</th>
<th>Intent</th><th>Args</th></tr>{ev_rows}</table>"""
```

- [ ] **Step 4: Edit `teluvane/routes/evidence.py`**

Replace both handlers:

```python
@router.get("/evidence/{session_id}", response_class=HTMLResponse)
def evidence(session_id: str, org_id: str = Depends(current_org)) -> str:
    events = store.events(org_id, session_id)
    verdicts = store.verdicts(org_id, session_id)
    anchor_dict = _evidence_anchor(org_id, session_id)
    canon = store.canonical_events(org_id, session_id) if anchor_dict else None
    report = store.verify_report(org_id, session_id)
    pack = build_evidence_pack(
        session_id,
        events,
        verdicts,
        framework=base_pack_for_org(org_id).framework,
        chain_intact=report["chain_intact"],
        anchor=anchor_dict,
        canonical=canon,
        erasure=report,
        openings=store.payload_openings(org_id, session_id),
    )
    return pack["html"]


@router.get("/evidence/{session_id}/pdf")
def evidence_pdf(session_id: str, org_id: str = Depends(current_org)) -> Response:
    # PDF export is a Starter/Pro perk (per the pricing page); free orgs get the HTML pack above.
    if org_plan(org_id) not in ("starter", "pro"):
        raise HTTPException(
            status_code=402, detail="PDF evidence export requires the Starter or Pro plan"
        )
    events = store.events(org_id, session_id)
    verdicts = store.verdicts(org_id, session_id)
    anchor_dict = _evidence_anchor(org_id, session_id)
    canon = store.canonical_events(org_id, session_id) if anchor_dict else None
    report = store.verify_report(org_id, session_id)
    pdf = build_evidence_pdf(
        session_id,
        events,
        verdicts,
        framework=base_pack_for_org(org_id).framework,
        chain_intact=report["chain_intact"],
        anchor=anchor_dict,
        canonical=canon,
        erasure=report,
        openings=store.payload_openings(org_id, session_id),
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{session_id}-evidence.pdf"'},
    )
```

- [ ] **Step 5: Edit `teluvane/tribunal.py`**

Replace `_events_to_text` so an erased event is shown as erased and never leaks stale content into a prompt:

```python
def _events_to_text(events: list[Event], max_chars: int = MAX_LOG_CHARS) -> str:
    lines = [
        f"#{e.seq} [{e.kind}] tool={e.tool} [payload erased]"
        if e.erased
        else (
            f"#{e.seq} [{e.kind}] tool={e.tool} intent={e.intent!r} "
            f"args={json.dumps(e.args, ensure_ascii=False)} "
            f"approved_by={e.approved_by} output={e.output[:OUTPUT_CHARS]!r}"
        )
        for e in events
    ]
    kept: list[str] = []
    total = 0
    for line in reversed(lines):  # newest first: recent actions matter most
        if total + len(line) + 1 > max_chars and kept:
            break
        kept.append(line)
        total += len(line) + 1
    kept.reverse()
    omitted = len(lines) - len(kept)
    if omitted:
        kept.insert(0, f"[{omitted} earlier events omitted to fit the context window]")
    return "\n".join(kept)
```

- [ ] **Step 6: Run the tests**

Run: `pytest tests/test_privacy_api.py tests/test_tribunal_erased.py tests/test_evidence.py -v` then `pytest -q`.
Expected: PASS.

- [ ] **Step 7: Format, lint, commit**

```bash
ruff format teluvane/evidence.py teluvane/routes/evidence.py teluvane/tribunal.py tests/test_privacy_api.py tests/test_tribunal_erased.py
ruff check --select E,F,I tests/test_tribunal_erased.py tests/test_privacy_api.py
git add teluvane tests
git commit -m "feat: evidence packs and the tribunal handle erased events"
```

---

### Task 6: Cross-language vector for the version 2 chain

**Files:**
- Modify: `tests/test_store_canonical.py`, `frontend/scripts/sync-vectors.mjs`, `frontend/lib/anchorVectors.test.ts`
- Create: `tests/fixtures/chain_vectors_v2.json` (generated), `frontend/lib/__fixtures__/chain_vectors_v2.json` (synced)

The browser `verifyChain` takes each event's canonical string verbatim and checks the hash and the `prev` link, so it verifies v2 chains without changes. This task proves it against a Python-generated vector, the same way v1 is proven.

- [ ] **Step 1: Add the Python test and generate the vector**

In `tests/test_store_canonical.py` add this constant under the existing `VECTORS = ...` line:

```python
VECTORS_V2 = pathlib.Path(__file__).parent / "fixtures" / "chain_vectors_v2.json"
```

and append this test:

```python
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
```

Generate only the v2 fixture. Do not run the whole file with the regen variable set: it would also rewrite the frozen v1 vector.

```bash
REGEN_ANCHOR_VECTORS=1 pytest tests/test_store_canonical.py::test_v2_canonical_roundtrip_and_vectors -v
git status --short tests/fixtures
```

Expected: PASS, and `tests/fixtures/chain_vectors_v2.json` is the only changed or new file under `tests/fixtures`. If `chain_vectors.json` shows as modified, run `git checkout tests/fixtures/chain_vectors.json`.

- [ ] **Step 2: Sync and test in the browser library**

In `frontend/scripts/sync-vectors.mjs` change the list to `["merkle_vectors.json", "chain_vectors.json", "chain_vectors_v2.json"]`. In `frontend/lib/anchorVectors.test.ts` add `import chainVectorsV2 from "./__fixtures__/chain_vectors_v2.json";` under the existing chain vectors import, and append:

```ts
describe("chain verify parity for erasable (v2) events", () => {
  it("verifies a v2 chain, whose canonical strings carry a commitment instead of content", async () => {
    for (const e of chainVectorsV2.events) {
      expect(JSON.parse(e.canonical).v).toBe(2);
      expect(e.canonical).not.toContain("intent");
    }
    const res = await verifyChain(chainVectorsV2.events);
    expect(res.ok).toBe(true);
    expect(res.head).toBe(chainVectorsV2.events.at(-1)!.hash);
  });
  it("flags a v2 event whose commitment was swapped", async () => {
    const evts = chainVectorsV2.events.map((e: any) => ({ ...e }));
    evts[1] = { ...evts[1], canonical: evts[1].canonical.replace(/"payload_commitment": "[0-9a-f]{4}/, '"payload_commitment": "0000') };
    const res = await verifyChain(evts);
    expect(res.ok).toBe(false);
    expect(res.failAt).toBe(evts[1].seq);
  });
});
```

```bash
cd frontend && npm run sync-vectors && npx vitest run lib/anchorVectors.test.ts && cd ..
```

Expected: PASS, 8 tests in that file.

- [ ] **Step 3: Commit**

```bash
git add tests/test_store_canonical.py tests/fixtures/chain_vectors_v2.json frontend/scripts/sync-vectors.mjs frontend/lib/anchorVectors.test.ts frontend/lib/__fixtures__/chain_vectors_v2.json
git commit -m "test: verify a version 2 chain vector in the browser library"
```

---

### Task 7: Documentation and a demo you can run

**Files:**
- Create: `docs/gdpr-and-immutable-logs.md`, `scripts/erasure_demo.py`
- Modify: `README.md`, `docs/investor/security-overview.md`

- [ ] **Step 1: Write the public page**

Create `docs/gdpr-and-immutable-logs.md`:

````markdown
# An unchangeable log and the right to erasure

TELUVANE records what an AI agent did in a hash-chained log, so that changing a record
afterwards is visible. Data protection law can require you to delete personal data on request.
These two goals look like they collide. This page explains how TELUVANE handles both, and where
it cannot help. It describes what the software does. It is not legal advice, and it does not
claim that using TELUVANE makes anyone compliant with the GDPR or any other law.

## The conflict

A plain hash chain digests the full content of every event. Delete or edit one event and its
hash no longer matches, so the whole chain from that point on fails verification. Any anchor
that was written to a public chain from that chain's head is also left pointing at data that no
longer exists. With such a design, erasing personal data means destroying the evidence.

## What TELUVANE does instead

Each event is split in two parts.

- **Structure**, which stays: the organization, agent id, session id, event kind, tool name,
  timestamp, and the link to the previous event.
- **Content**, which can be erased: the stated intent, the tool arguments, the output, and the
  approval field.

The chain does not digest the content. It digests a **salted commitment** to it: a SHA-256
hash over a random 32-byte salt and the content. The content and its salt are stored in a
separate table. Erasing an event deletes that row.

After erasure:

- every hash in the chain, and every anchored chain head, is unchanged, so the chain still
  verifies;
- the commitment that remains cannot be turned back into the content, because the random salt
  is gone with it;
- the event still exists as a record that something happened at that time, by that agent,
  through that tool, but what it said is gone.

Before erasure, verification also checks that the stored content still matches its commitment,
so editing the content in the database is caught exactly as it was before.

## What stays, and what goes

| Kept after erasure | Removed by erasure |
|---|---|
| Organization, agent id, session id | Intent text |
| Event kind and tool name | Tool arguments |
| Timestamp and hash links | Tool output |
| The salted commitment | Approval field (may hold a user id) |
| Token counts and cost | The salt |
| An entry in the erasure log (event numbers, who asked, why, when) | Verdict explanations for the session (replaced with a redaction notice) |

Because the kept fields are not erased, do not put personal data in agent ids, session ids or
tool names.

## Erasing

Only the organization owner can erase. Erase every event of a session, or chosen events:

```bash
curl -X POST "$TELUVANE_URL/sessions/$SESSION_ID/erase" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"reason": "data subject request 2026-10-01"}'

curl -X POST "$TELUVANE_URL/sessions/$SESSION_ID/erase" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"seqs": [41, 42], "reason": "one event only"}'
```

The response counts what happened: `erased`, `already_erased`, and `legacy_unerasable`.

Verifying afterwards:

```bash
curl "$TELUVANE_URL/verify?session_id=$SESSION_ID" -H "Authorization: Bearer $TOKEN"
# {"chain_intact": true, "erased_events": 3, "unexplained_erasures": 0}
```

`unexplained_erasures` counts events whose content is missing but that no erasure log entry
covers. A non-zero value means content was removed some other way than the erase endpoint, and
the session should be treated as suspect until someone explains it.

## Retention and legal hold

An organization can set a retention window. Content older than that many days is erased
automatically, once an hour, the same way as a manual erasure:

```bash
curl -X PUT "$TELUVANE_URL/orgs/retention" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"retention_days": 180, "legal_hold": false}'
```

Setting `legal_hold` to `true` blocks both the automatic job and manual erasure for the whole
organization until it is set back to `false`. Use it when you are required to keep records, for
example during a dispute or an investigation. Deciding which duty wins (a request to erase or a
duty to keep records) is your decision with your counsel. TELUVANE only provides the switches.

## What this does not cover

- **Events recorded before this feature.** Older events (hash version 1) have their content
  inside the hash. They cannot be erased without breaking the chain, and the erase endpoint says
  so instead of skipping them silently.
- **Copies outside TELUVANE.** Evidence packs, PDFs and webhook deliveries you already exported
  or received, database backups held by the hosting provider until they rotate, and any text
  sent to a model provider when the live tribunal ran on your Anthropic key.
- **The kept fields** listed above.
- **Proof that an erasure was authorized.** Missing content looks the same whether the owner
  erased it or someone with database access deleted it. The erasure log and the
  `unexplained_erasures` counter make the second case visible, but the erasure log is not itself
  tamper-evident yet.
- **On-chain anchors.** Nothing personal is ever written on chain, only Merkle roots of chain
  heads, so there is nothing there to erase.

## Checking the design

The design and its alternatives are in
`docs/superpowers/specs/2026-09-27-erasable-event-log-design.md`. The tests that pin the
properties above are `tests/test_event_commitments.py`, `tests/test_erasure.py` and
`tests/test_privacy_api.py`. You can watch the whole thing happen on a scratch database with
`python scripts/erasure_demo.py`.
````

- [ ] **Step 2: Create the demo script**

Create `scripts/erasure_demo.py`:

```python
"""Live demo of GDPR erasure on a hash-chained log. Needs DATABASE_URL (a throwaway database).

    python scripts/erasure_demo.py

Records a session containing personal data, verifies the chain, erases the personal content,
and shows the chain still verifies with identical hashes. Everything is cleaned up at the end.
"""

import secrets

from teluvane.db import get_pool
from teluvane.migrate import apply_migrations
from teluvane.schema import Event
from teluvane.store import Store


def main() -> None:
    apply_migrations()
    store = Store()
    org = "demo-" + secrets.token_hex(4)
    session = "erasure-demo"
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO orgs(id,name,owner_user_id) VALUES(%s,'demo','demo')", (org,))
        conn.commit()
    try:
        for intent, args in [
            ("look up the customer", {"name": "Jane Doe", "email": "jane@example.com"}),
            ("record their national id", {"ssn": "078-05-1120"}),
            ("send confirmation", {"to": "jane@example.com", "body": "Your request is done."}),
        ]:
            store.append(
                org,
                Event(
                    agent_id="demo",
                    session_id=session,
                    kind="tool_call",
                    tool="crm",
                    intent=intent,
                    args=args,
                    approved_by="human:demo",
                ),
            )
        heads_before = [r["hash"] for r in store.canonical_events(org, session)]
        print("1. recorded 3 events with personal data")
        print("   chain:", store.verify_report(org, session))
        print("   event 2 args:", store.events(org, session)[1].args)

        result = store.erase_payloads(org, session, requested_by="demo", reason="art 17 request")
        print("\n2. erased on request:", result)

        events = store.events(org, session)
        print("   event 2 args:", events[1].args, "| erased:", events[1].erased)
        print("   chain:", store.verify_report(org, session))
        same = heads_before == [r["hash"] for r in store.canonical_events(org, session)]
        print("   every hash identical to before erasure:", same)
    finally:
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM erasure_log WHERE org_id=%s", (org,))
            cur.execute("DELETE FROM events WHERE org_id=%s", (org,))
            cur.execute("DELETE FROM orgs WHERE id=%s", (org,))
            conn.commit()


if __name__ == "__main__":
    main()
```

Run it against a throwaway database (never production): `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/teluvane_test python scripts/erasure_demo.py`.
Expected: `chain: {'chain_intact': True, 'erased_events': 0, ...}`, then after erasure `event 2 args: {} | erased: True`, `chain: {'chain_intact': True, 'erased_events': 3, 'unexplained_erasures': 0}` and `every hash identical to before erasure: True`. This output is what to show a reviewer.

- [ ] **Step 3: README**

In the "How it works" table of `README.md`, add this row after the Evidence pack row:

```
| **Privacy controls** | The chain hashes a salted commitment to each event's content (intent, arguments, output, approval) instead of the content. The owner can erase content per session, or set a retention window and a legal hold, and the chain and on-chain anchors keep verifying. See [docs/gdpr-and-immutable-logs.md](docs/gdpr-and-immutable-logs.md). This is a mechanism, not a compliance claim. |
```

In the "Tests" section, add `content commitments, erasure and retention,` to the coverage sentence.

- [ ] **Step 4: Security overview**

In `docs/investor/security-overview.md` add this section before "## Secrets and encryption":

```
## Personal data and erasure
Recorded content (intent, tool arguments, output, approval field) can be erased per session, or
automatically after a retention window, while the hash chain and any on-chain anchors keep
verifying. The chain hash covers a salted commitment to the content instead of the content
itself. Fields that are kept (ids, tool name, timestamps, the commitment), and what erasure does
not cover (exports, provider backups, model-provider copies, events recorded before this
feature), are listed in docs/gdpr-and-immutable-logs.md. This is a mechanism, not a claim that
any customer is compliant with any law.
```

- [ ] **Step 5: Guard the wording, then commit**

```bash
grep -rniI "gdpr.compliant\|makes you compliant\|fully compliant" README.md docs frontend/app frontend/components frontend/public || echo "no compliance claims"
git diff master --name-only | xargs grep -nI "$(printf '\xe2\x80\x94')" || echo "no em dashes"
ruff format scripts/erasure_demo.py && ruff check --select E,F,I scripts/erasure_demo.py
git add docs README.md scripts/erasure_demo.py
git commit -m "docs: how erasure works with an unchangeable log, plus a runnable demo"
```

---

### Task 8: Roll out safely

No code. This is the deploy runbook. The API does not apply migrations on boot (`DEPLOY.md`, `Dockerfile`), so order matters.

- [ ] **Step 1: Confirm CI is green** on the pull request from `plan3/erasable-log` (secrets scan, backend, frontend, contracts).
- [ ] **Step 2: Confirm a restorable backup exists** for the production database before touching it. Check what your Supabase plan provides, or take a `pg_dump`. Ask the maintainer if unsure. Do not skip this.
- [ ] **Step 3: Migrate production first**, from a machine with the production `DATABASE_URL` (transaction pooler, as in `DEPLOY.md`):

```bash
DATABASE_URL="postgresql://postgres:<pwd>@<host>:6543/postgres" \
  python -c "from teluvane.migrate import apply_migrations; print(apply_migrations())"
```

Expected output includes `0014_erasable_payloads.sql`. The old API keeps working against the new schema because the migration only adds columns with defaults and new tables.
- [ ] **Step 4: Merge and deploy the API.** Watch Render's health check (`/health`, `/ready`).
- [ ] **Step 5: Smoke test the write path.** Post one event with a real API key and confirm `"hash_version":2` in the response:

```bash
curl -s -X POST "$TELUVANE_URL/events" -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"agent_id":"smoke","session_id":"smoke-1","kind":"llm_call","intent":"smoke test"}'
```

- [ ] **Step 6: Smoke test verify and erase** with an owner's Supabase access token in `$TOKEN`: `GET /verify?session_id=smoke-1` returns `{"chain_intact": true, "erased_events": 0, "unexplained_erasures": 0}`; `POST /sessions/smoke-1/erase` returns `erased: 1`; `GET /verify?session_id=smoke-1` returns `erased_events: 1`, `chain_intact: true`. Open the dashboard and confirm an old session still loads and verifies.
- [ ] **Step 7: If anchoring is configured,** confirm a Pro session recorded after the deploy still anchors and its public `/verify` page passes. If anchoring is not configured in production, say so in the pull request instead of skipping silently.
- [ ] **Step 8: Rollback plan, if anything looks wrong:** set `TELUVANE_EVENT_HASH_VERSION=1` on Render and redeploy. New events are written as version 1 again and existing version 2 events keep verifying. There is no down migration and none is needed.
