# Avalanche On-Chain Anchoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Anchor each TELUVANE session's SHA-256 hash-chain head, Merkle-batched, to a `SessionAnchorRegistry` contract on Avalanche Fuji, so anyone can verify a session log is unaltered by reading Avalanche directly, without trusting TELUVANE.

**Architecture:** A pure-Python Merkle module builds one tree per batch of finalized sessions. `teluvane/anchor.py` persists batch membership + per-session proofs in one DB transaction, then submits a single `anchorBatch` transaction via `web3.py`; a reconcile pass waits N confirmations. Verification (dashboard panel, public page, evidence pack) recomputes the chain head from server-supplied canonical digest strings, recomputes the Merkle root, and reads `anchoredAt(root)` from a public Fuji RPC. The existing per-event `_event_digest` is not changed.

**Tech Stack:** Python 3.11, FastAPI, psycopg 3, `web3>=7.0`, `py-solc-x` (dev), Solidity 0.8.24 + Foundry (CI), Next.js 16 / React 19, `viem`, vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-avalanche-anchoring-design.md`

## Global Constraints

- `teluvane/store.py::_event_digest` MUST NOT change its output bytes. Refactor only by extracting a helper that produces the identical canonical string.
- Every `Store` method takes `org_id` first; `Store._assert_scoped(org_id, sql)` must pass for every SQL string a `Store` method runs (it raises unless the SQL text contains `org_id`). `anchor_batches` queries run outside `Store` (module-level helpers in `anchor.py`) because that table is global.
- Anchoring is Pro-plan only: gate on `teluvane.billing.org_plan(org_id) == "pro"`.
- Feature is inert when env is unset: `anchor.chain_config()` returns `None` and no code path raises.
- Migrations: add `migrations/0012_onchain_anchor.sql`. Applied lexically, once, by `teluvane/migrate.py`. Use `CREATE TABLE IF NOT EXISTS`.
- No em dashes anywhere (code, comments, commits, docs). Use commas/periods/parentheses.
- UI: no `rounded-full` status pills, no gradients, no glass, one accent color. Status = colored dot + text.
- Merkle domain-separation prefixes are fixed strings: leaf `teluvane-anchor-leaf-v1:`, node `teluvane-anchor-node-v1:`.
- Leaf value: `sha256(prefix + org_id + b"|" + session_id + b"|" + chain_head_hex)` (all UTF-8 bytes).
- Node value: `sha256(prefix + lo + ro)` where `(lo, ro) = sorted((left_bytes, right_bytes))`.
- Confirmations default: 5. Chain id: 43113.
- Python test DB is truncated per-test via the `store` fixture; new tables must be added to any `TRUNCATE` the tests rely on (see Task 1).

---

### Task 1: Migration 0012 + anchor store helpers

**Files:**
- Create: `migrations/0012_onchain_anchor.sql`
- Create: `teluvane/anchor_store.py`
- Test: `tests/test_anchor_store.py`
- Modify: `tests/conftest.py` (add new tables to the `store` fixture TRUNCATE)

**Interfaces:**
- Consumes: `teluvane.db.get_pool`
- Produces:
  - `anchor_store.insert_batch(pool, root: str, chain_id: int, session_count: int) -> int` (returns batch id, status `pending`)
  - `anchor_store.insert_session_anchor(pool, org_id: str, session_id: str, through_seq: int, batch_id: int, chain_head: str, proof: list[str]) -> None`
  - `anchor_store.mark_submitted(pool, batch_id: int, tx_hash: str) -> None`
  - `anchor_store.mark_mined(pool, batch_id: int, block_number: int, gas_used: int, fee_wei: int, confirmations: int) -> None`
  - `anchor_store.mark_failed(pool, batch_id: int) -> None` (also deletes that batch's `session_anchors` rows)
  - `anchor_store.batches_by_status(pool, *statuses: str) -> list[dict]`
  - `anchor_store.latest_anchor(pool, org_id: str, session_id: str) -> dict | None`
  - `anchor_store.anchor_for_seq(pool, org_id: str, session_id: str, through_seq: int) -> dict | None`
  - `anchor_store.max_anchored_seq(pool, org_id: str, session_id: str) -> int` (0 if none)
  - `anchor_store.set_public(pool, org_id: str, session_id: str, public: bool) -> None`
  - `anchor_store.is_public(pool, org_id: str, session_id: str) -> bool`

- [ ] **Step 1: Write the migration SQL**

`migrations/0012_onchain_anchor.sql`:

```sql
-- 0012: on-chain anchoring of session integrity chains

CREATE TABLE IF NOT EXISTS anchor_batches (
    id            BIGSERIAL PRIMARY KEY,
    root          TEXT NOT NULL UNIQUE,
    chain_id      INTEGER NOT NULL,
    tx_hash       TEXT,
    block_number  BIGINT,
    confirmations INTEGER NOT NULL DEFAULT 0,
    session_count INTEGER NOT NULL,
    gas_used      BIGINT,
    fee_wei       NUMERIC,
    status        TEXT NOT NULL DEFAULT 'pending',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at  TIMESTAMPTZ,
    mined_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS session_anchors (
    org_id               TEXT NOT NULL,
    session_id           TEXT NOT NULL,
    anchored_through_seq  BIGINT NOT NULL,
    batch_id             BIGINT NOT NULL REFERENCES anchor_batches(id),
    chain_head           TEXT NOT NULL,
    proof                JSONB NOT NULL DEFAULT '[]',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, session_id, anchored_through_seq)
);
CREATE INDEX IF NOT EXISTS idx_session_anchors_batch ON session_anchors (batch_id);
CREATE INDEX IF NOT EXISTS idx_session_anchors_lookup ON session_anchors (org_id, session_id);

CREATE TABLE IF NOT EXISTS session_anchor_public (
    org_id      TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    PRIMARY KEY (org_id, session_id)
);
```

- [ ] **Step 2: Add tables to the test truncation**

In `tests/conftest.py`, change the `store` fixture's TRUNCATE to also clear the new tables:

```python
cur.execute("TRUNCATE events, verdicts, api_keys, org_members, orgs, "
            "anchor_batches, session_anchors, session_anchor_public RESTART IDENTITY CASCADE")
```

- [ ] **Step 3: Write the failing test**

`tests/test_anchor_store.py`:

```python
import json
from teluvane import anchor_store
from teluvane.db import get_pool


def _truncate():
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE anchor_batches, session_anchors, session_anchor_public RESTART IDENTITY CASCADE")
        conn.commit()


def test_batch_lifecycle_and_anchor_lookup():
    _truncate()
    pool = get_pool()
    bid = anchor_store.insert_batch(pool, "0xabc", 43113, 2)
    assert isinstance(bid, int)
    anchor_store.insert_session_anchor(pool, "org1", "sess1", 5, bid, "deadbeef", ["0x11"])
    anchor_store.insert_session_anchor(pool, "org2", "sess9", 3, bid, "cafe", [])

    assert anchor_store.max_anchored_seq(pool, "org1", "sess1") == 5
    assert anchor_store.max_anchored_seq(pool, "org1", "missing") == 0
    latest = anchor_store.latest_anchor(pool, "org1", "sess1")
    assert latest["chain_head"] == "deadbeef"
    assert latest["proof"] == ["0x11"]
    assert latest["status"] == "pending"

    anchor_store.mark_submitted(pool, bid, "0xtx")
    anchor_store.mark_mined(pool, bid, 100, 21000, 1234, 6)
    latest = anchor_store.latest_anchor(pool, "org1", "sess1")
    assert latest["status"] == "mined"
    assert latest["tx_hash"] == "0xtx"
    assert latest["block_number"] == 100


def test_mark_failed_removes_session_anchors():
    _truncate()
    pool = get_pool()
    bid = anchor_store.insert_batch(pool, "0xdef", 43113, 1)
    anchor_store.insert_session_anchor(pool, "org1", "sess1", 5, bid, "aa", [])
    anchor_store.mark_failed(pool, bid)
    assert anchor_store.latest_anchor(pool, "org1", "sess1") is None
    assert anchor_store.batches_by_status(pool, "failed")[0]["root"] == "0xdef"


def test_public_toggle():
    _truncate()
    pool = get_pool()
    assert anchor_store.is_public(pool, "org1", "sess1") is False
    anchor_store.set_public(pool, "org1", "sess1", True)
    assert anchor_store.is_public(pool, "org1", "sess1") is True
    anchor_store.set_public(pool, "org1", "sess1", False)
    assert anchor_store.is_public(pool, "org1", "sess1") is False
```

- [ ] **Step 4: Run the test, verify it fails**

Run: `pytest tests/test_anchor_store.py -v`
Expected: FAIL (`ModuleNotFoundError: teluvane.anchor_store`)

- [ ] **Step 5: Implement `teluvane/anchor_store.py`**

```python
"""Postgres helpers for the on-chain anchoring tables. These tables are global
(anchor_batches spans orgs); session_anchors is still org-scoped by column.
Kept out of Store because Store._assert_scoped rejects any SQL without an
org_id predicate, and anchor_batches has none."""
import json
from psycopg.rows import dict_row


def insert_batch(pool, root: str, chain_id: int, session_count: int) -> int:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO anchor_batches(root, chain_id, session_count) "
            "VALUES(%s,%s,%s) RETURNING id", (root, chain_id, session_count))
        bid = cur.fetchone()[0]
        conn.commit()
        return bid


def insert_session_anchor(pool, org_id: str, session_id: str, through_seq: int,
                          batch_id: int, chain_head: str, proof: list) -> None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO session_anchors"
            "(org_id, session_id, anchored_through_seq, batch_id, chain_head, proof) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (org_id, session_id, through_seq, batch_id, chain_head, json.dumps(proof)))
        conn.commit()


def mark_submitted(pool, batch_id: int, tx_hash: str) -> None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE anchor_batches SET status='submitted', tx_hash=%s, submitted_at=now() "
            "WHERE id=%s", (tx_hash, batch_id))
        conn.commit()


def mark_mined(pool, batch_id: int, block_number: int, gas_used: int,
               fee_wei: int, confirmations: int) -> None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE anchor_batches SET status='mined', block_number=%s, gas_used=%s, "
            "fee_wei=%s, confirmations=%s, mined_at=now() WHERE id=%s",
            (block_number, gas_used, fee_wei, confirmations, batch_id))
        conn.commit()


def mark_failed(pool, batch_id: int) -> None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM session_anchors WHERE batch_id=%s", (batch_id,))
        cur.execute("UPDATE anchor_batches SET status='failed' WHERE id=%s", (batch_id,))
        conn.commit()


def update_confirmations(pool, batch_id: int, block_number: int, confirmations: int) -> None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE anchor_batches SET block_number=%s, confirmations=%s WHERE id=%s",
                    (block_number, confirmations, batch_id))
        conn.commit()


def batches_by_status(pool, *statuses: str) -> list:
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM anchor_batches WHERE status = ANY(%s) ORDER BY id",
                    (list(statuses),))
        return cur.fetchall()


def _anchor_row(pool, sql: str, params: tuple) -> dict | None:
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return dict(row) if row else None


_JOIN = ("SELECT sa.*, b.status, b.tx_hash, b.block_number, b.confirmations, "
         "b.mined_at, b.chain_id FROM session_anchors sa "
         "JOIN anchor_batches b ON b.id = sa.batch_id "
         "WHERE sa.org_id=%s AND sa.session_id=%s")


def latest_anchor(pool, org_id: str, session_id: str) -> dict | None:
    return _anchor_row(pool, _JOIN + " ORDER BY sa.anchored_through_seq DESC LIMIT 1",
                       (org_id, session_id))


def anchor_for_seq(pool, org_id: str, session_id: str, through_seq: int) -> dict | None:
    return _anchor_row(pool, _JOIN + " AND sa.anchored_through_seq=%s",
                       (org_id, session_id, through_seq))


def max_anchored_seq(pool, org_id: str, session_id: str) -> int:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(anchored_through_seq), 0) FROM session_anchors "
                    "WHERE org_id=%s AND session_id=%s", (org_id, session_id))
        return int(cur.fetchone()[0])


def set_public(pool, org_id: str, session_id: str, public: bool) -> None:
    with pool.connection() as conn, conn.cursor() as cur:
        if public:
            cur.execute("INSERT INTO session_anchor_public(org_id, session_id) VALUES(%s,%s) "
                        "ON CONFLICT DO NOTHING", (org_id, session_id))
        else:
            cur.execute("DELETE FROM session_anchor_public WHERE org_id=%s AND session_id=%s",
                        (org_id, session_id))
        conn.commit()


def is_public(pool, org_id: str, session_id: str) -> bool:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM session_anchor_public WHERE org_id=%s AND session_id=%s",
                    (org_id, session_id))
        return cur.fetchone() is not None
```

- [ ] **Step 6: Run the test, verify it passes**

Run: `pytest tests/test_anchor_store.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Run the full suite to confirm no regression from the conftest change**

Run: `pytest -q`
Expected: PASS (all existing tests still green)

- [ ] **Step 8: Commit**

```bash
git add migrations/0012_onchain_anchor.sql teluvane/anchor_store.py tests/test_anchor_store.py tests/conftest.py
git commit -m "feat: anchor storage schema and helpers"
```

---

### Task 2: Pure-Python Merkle module + cross-language test vectors

**Files:**
- Create: `teluvane/merkle.py`
- Test: `tests/test_merkle.py`
- Create: `tests/fixtures/merkle_vectors.json` (generated by the test, committed)

**Interfaces:**
- Produces:
  - `merkle.leaf_hash(org_id: str, session_id: str, chain_head_hex: str) -> bytes`
  - `merkle.build_tree(leaves: list[tuple[str, str, str]]) -> tuple[str, dict[tuple[str, str], list[str]]]` (returns `("0x"+root_hex, {(org,session): ["0x"+sibling, ...]})`)
  - `merkle.verify_proof(org_id: str, session_id: str, chain_head_hex: str, proof: list[str], root_hex: str) -> bool`
  - `merkle.LEAF_PREFIX`, `merkle.NODE_PREFIX` (bytes constants)

- [ ] **Step 1: Write the failing test**

`tests/test_merkle.py`:

```python
import json
import pathlib
import hashlib
from teluvane import merkle

VECTORS = pathlib.Path(__file__).parent / "fixtures" / "merkle_vectors.json"


def _naive_root(leaves_bytes):
    level = list(leaves_bytes)
    if len(level) == 1:
        return level[0]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            if i + 1 == len(level):
                nxt.append(level[i])
            else:
                lo, ro = sorted((level[i], level[i + 1]))
                nxt.append(hashlib.sha256(merkle.NODE_PREFIX + lo + ro).digest())
        level = nxt
    return level[0]


def test_single_leaf_root_is_leaf_and_empty_proof():
    root, proofs = merkle.build_tree([("o", "s", "aa")])
    assert proofs[("o", "s")] == []
    assert root == "0x" + merkle.leaf_hash("o", "s", "aa").hex()
    assert merkle.verify_proof("o", "s", "aa", [], root)


def test_leaf_binding_distinguishes_sessions_with_same_head():
    a = merkle.leaf_hash("o", "s1", "aa")
    b = merkle.leaf_hash("o", "s2", "aa")
    assert a != b


def test_even_and_odd_counts_match_naive_and_proofs_verify():
    for n in (2, 3, 4, 5, 8):
        leaves = [("o", f"s{i}", f"{i:064x}") for i in range(n)]
        root, proofs = merkle.build_tree(leaves)
        leaf_bytes = [merkle.leaf_hash(o, s, h) for o, s, h in leaves]
        assert root == "0x" + _naive_root(leaf_bytes).hex()
        for o, s, h in leaves:
            assert merkle.verify_proof(o, s, h, proofs[(o, s)], root)


def test_tampered_head_fails_verification():
    leaves = [("o", f"s{i}", f"{i:064x}") for i in range(4)]
    root, proofs = merkle.build_tree(leaves)
    assert not merkle.verify_proof("o", "s0", "ff" * 32, proofs[("o", "s0")], root)


def test_emit_vectors_file():
    # Regenerates the fixture the TypeScript port tests against. Committed to the repo.
    cases = []
    for n in (1, 2, 3, 5):
        leaves = [("org-é", f"sess-{i}", f"{i:064x}") for i in range(n)]
        root, proofs = merkle.build_tree(leaves)
        cases.append({
            "leaves": [{"org_id": o, "session_id": s, "chain_head": h} for o, s, h in leaves],
            "root": root,
            "proofs": [proofs[(o, s)] for o, s, _ in leaves],
        })
    VECTORS.parent.mkdir(parents=True, exist_ok=True)
    VECTORS.write_text(json.dumps({"cases": cases}, indent=2, ensure_ascii=False))
    assert VECTORS.exists()
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `pytest tests/test_merkle.py -v`
Expected: FAIL (`ModuleNotFoundError: teluvane.merkle`)

- [ ] **Step 3: Implement `teluvane/merkle.py`**

```python
"""Order-independent binary Merkle tree over session chain heads.

Leaf  = sha256(LEAF_PREFIX + org_id + b"|" + session_id + b"|" + chain_head_hex)
Node  = sha256(NODE_PREFIX + lo + ro), where (lo, ro) = sorted((left, right))
Odd node at a level is promoted unchanged.

Sorted pairs mean a proof is just a list of sibling digests, no left/right flags.
The prefixes are domain separators: a leaf digest can never be read as a node.
"""
import hashlib

LEAF_PREFIX = b"teluvane-anchor-leaf-v1:"
NODE_PREFIX = b"teluvane-anchor-node-v1:"


def leaf_hash(org_id: str, session_id: str, chain_head_hex: str) -> bytes:
    payload = (LEAF_PREFIX + org_id.encode("utf-8") + b"|"
               + session_id.encode("utf-8") + b"|" + chain_head_hex.encode("utf-8"))
    return hashlib.sha256(payload).digest()


def _node(left: bytes, right: bytes) -> bytes:
    lo, ro = sorted((left, right))
    return hashlib.sha256(NODE_PREFIX + lo + ro).digest()


def build_tree(leaves):
    if not leaves:
        raise ValueError("cannot build a Merkle tree from zero leaves")
    nodes = [leaf_hash(o, s, h) for o, s, h in leaves]
    # proof_paths[i] accumulates the sibling digests for leaf i, bottom up.
    proof_paths = [[] for _ in leaves]
    index_at_level = list(range(len(leaves)))
    level = nodes
    while len(level) > 1:
        nxt = []
        nxt_index = []
        for i in range(0, len(level), 2):
            if i + 1 == len(level):
                nxt.append(level[i])
            else:
                nxt.append(_node(level[i], level[i + 1]))
            nxt_index.append(i)
        for leaf_i, pos in enumerate(index_at_level):
            if pos is None:
                continue
            sib = pos ^ 1
            if sib < len(level) and sib != pos:
                proof_paths[leaf_i].append("0x" + level[sib].hex())
            # new position of this leaf's ancestor
            index_at_level[leaf_i] = pos // 2
        level = nxt
    root = "0x" + level[0].hex()
    proofs = {(leaves[i][0], leaves[i][1]): proof_paths[i] for i in range(len(leaves))}
    return root, proofs


def verify_proof(org_id: str, session_id: str, chain_head_hex: str,
                 proof, root_hex: str) -> bool:
    acc = leaf_hash(org_id, session_id, chain_head_hex)
    for sib_hex in proof:
        sib = bytes.fromhex(sib_hex[2:] if sib_hex.startswith("0x") else sib_hex)
        acc = _node(acc, sib)
    return ("0x" + acc.hex()) == (root_hex if root_hex.startswith("0x") else "0x" + root_hex)
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `pytest tests/test_merkle.py -v`
Expected: PASS (5 tests). `tests/fixtures/merkle_vectors.json` is created.

- [ ] **Step 5: Commit**

```bash
git add teluvane/merkle.py tests/test_merkle.py tests/fixtures/merkle_vectors.json
git commit -m "feat: Merkle tree module for anchor batches"
```

---

### Task 3: Expose the canonical event-digest string

**Files:**
- Modify: `teluvane/store.py:9-17` (extract `_event_canonical`, keep `_event_digest` output identical)
- Modify: `teluvane/store.py` (add `Store.canonical_events`)
- Test: `tests/test_store_canonical.py`
- Create: `tests/fixtures/chain_vectors.json` (generated by the test, committed)

**Interfaces:**
- Consumes: `Event` from `teluvane.schema`
- Produces:
  - `store._event_canonical(prev_hash: str, e: Event) -> str` (the exact string `_event_digest` hashes)
  - `Store.canonical_events(org_id: str, session_id: str) -> list[dict]` -> `[{"seq": int, "prev_hash": str, "hash": str, "canonical": str}, ...]` ordered by seq

- [ ] **Step 1: Write the failing test**

`tests/test_store_canonical.py`:

```python
import hashlib
import json
import pathlib
from teluvane.store import Store, _event_digest, _event_canonical
from teluvane.schema import Event

VECTORS = pathlib.Path(__file__).parent / "fixtures" / "chain_vectors.json"


def test_canonical_string_hashes_to_the_same_digest():
    e = Event(agent_id="a", session_id="s", kind="tool_call", tool="shell",
              args={"cmd": "ls", "u": "é"}, intent="look")
    e.org_id = "org1"
    canon = _event_canonical("GENESIS", e)
    assert hashlib.sha256(canon.encode("utf-8")).hexdigest() == _event_digest("GENESIS", e)
    assert json.loads(canon)["prev"] == "GENESIS"


def test_canonical_events_roundtrip(store):
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO orgs(id,name,owner_user_id) VALUES('org1','o','u') "
                    "ON CONFLICT DO NOTHING")
        conn.commit()
    for i in range(3):
        store.append("org1", Event(agent_id="a", session_id="s1", kind="llm_call",
                                   intent=f"step {i}"))
    rows = store.canonical_events("org1", "s1")
    assert [r["seq"] for r in rows] == sorted(r["seq"] for r in rows)
    prev = "GENESIS"
    for r in rows:
        assert hashlib.sha256(r["canonical"].encode("utf-8")).hexdigest() == r["hash"]
        assert json.loads(r["canonical"])["prev"] == prev
        prev = r["hash"]

    # emit the fixture for the TS port
    VECTORS.write_text(json.dumps({"events": rows}, indent=2, ensure_ascii=False))
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `pytest tests/test_store_canonical.py -v`
Expected: FAIL (`ImportError: cannot import name '_event_canonical'`)

- [ ] **Step 3: Refactor `_event_digest` and add `canonical_events`**

Replace `teluvane/store.py:9-17` with:

```python
def _event_canonical(prev_hash: str, e: Event) -> str:
    # The exact string the hash chain digests. org_id is included so an event is
    # cryptographically bound to its tenant. Output bytes are frozen: changing
    # this invalidates every stored chain.
    return json.dumps({
        "prev": prev_hash, "org_id": e.org_id, "agent_id": e.agent_id,
        "session_id": e.session_id, "kind": e.kind, "intent": e.intent,
        "tool": e.tool, "args": e.args, "output": e.output,
        "approved_by": e.approved_by, "ts": e.ts,
    }, sort_keys=True, ensure_ascii=False)


def _event_digest(prev_hash: str, e: Event) -> str:
    return hashlib.sha256(_event_canonical(prev_hash, e).encode("utf-8")).hexdigest()
```

Add this method to `Store` (next to `verify_chain`):

```python
    def canonical_events(self, org_id: str, session_id: str) -> list[dict]:
        """Per-event digest inputs for independent (browser) verification. The
        caller hashes `canonical` and checks it equals `hash`, then checks the
        chain links, without trusting this server to have hashed correctly."""
        out = []
        prev = "GENESIS"
        for e in self.events(org_id, session_id):
            out.append({"seq": e.seq, "prev_hash": prev, "hash": e.hash,
                        "canonical": _event_canonical(prev, e)})
            prev = e.hash
        return out
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `pytest tests/test_store_canonical.py -v`
Expected: PASS (2 tests). `tests/fixtures/chain_vectors.json` created.

- [ ] **Step 5: Run the store + recorder + evidence suites**

Run: `pytest tests/test_store.py tests/test_recorder.py tests/test_evidence.py -q`
Expected: PASS (digest output unchanged, nothing else touched)

- [ ] **Step 6: Commit**

```bash
git add teluvane/store.py tests/test_store_canonical.py tests/fixtures/chain_vectors.json
git commit -m "feat: expose canonical event-digest string for browser verification"
```

---

### Task 4: `AnchorConfig`, `chain_config()`, and `pending_leaves()`

**Files:**
- Create: `teluvane/anchor.py`
- Test: `tests/test_anchor_pending.py`
- Modify: `pyproject.toml` (add `web3>=7.0` to `dependencies`, `py-solc-x` to `dev`)

**Interfaces:**
- Consumes: `anchor_store.max_anchored_seq`, `teluvane.billing.org_plan`, `teluvane.db.get_pool`
- Produces:
  - `anchor.AnchorConfig` dataclass with the fields listed in the spec (§4), defaults: `chain_id=43113`, `min_session_age_minutes=30`, `batch_interval_minutes=10`, `confirmations=5`, `submit_timeout_minutes=30`, `low_balance_alert_avax=0.05`, `max_forced_runs_per_org_per_month=20`, `forced_run_cooldown_minutes=5`, `explorer_tx_url="https://testnet.snowtrace.io/tx/"`
  - `anchor.chain_config() -> AnchorConfig | None`
  - `anchor.pending_leaves(pool, cfg) -> list[tuple[str, str, int, str]]` -> `(org_id, session_id, through_seq, chain_head)`

- [ ] **Step 1: Add dependencies**

In `pyproject.toml`: add `"web3>=7.0",` to `[project].dependencies`; change the dev extra to `dev = ["pytest>=8.0", "respx>=0.21", "py-solc-x>=2.0"]`.

- [ ] **Step 2: Write the failing test**

`tests/test_anchor_pending.py`:

```python
import time
from datetime import datetime, timedelta, timezone
from teluvane import anchor
from teluvane.db import get_pool
from teluvane.schema import Event
from teluvane.store import Store


CFG = anchor.AnchorConfig(rpc_url="x", contract_address="0x0", signer_key="0x0",
                          min_session_age_minutes=30)


def _mk_org(plan="pro"):
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE events, orgs, org_members, anchor_batches, session_anchors "
                    "RESTART IDENTITY CASCADE")
        cur.execute("INSERT INTO orgs(id,name,owner_user_id) VALUES('org1','o','u')")
        if plan == "pro":
            cur.execute("INSERT INTO org_subscriptions(org_id, plan, status) "
                        "VALUES('org1','pro','active') ON CONFLICT (org_id) DO UPDATE SET plan='pro'")
        conn.commit()


def _age_session(session_id, minutes):
    old = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE events SET ts=%s WHERE session_id=%s", (old, session_id))
        conn.commit()


def test_quiet_pro_session_is_pending():
    _mk_org("pro")
    s = Store()
    for i in range(2):
        s.append("org1", Event(agent_id="a", session_id="s1", kind="llm_call", intent=str(i)))
    _age_session("s1", 45)
    leaves = anchor.pending_leaves(get_pool(), CFG)
    assert len(leaves) == 1
    org_id, session_id, through_seq, chain_head = leaves[0]
    assert (org_id, session_id) == ("org1", "s1")
    assert through_seq == 2
    assert len(chain_head) == 64


def test_recent_session_is_not_pending():
    _mk_org("pro")
    s = Store()
    s.append("org1", Event(agent_id="a", session_id="s2", kind="llm_call", intent="x"))
    leaves = anchor.pending_leaves(get_pool(), CFG)
    assert leaves == []


def test_free_plan_session_is_not_pending():
    _mk_org("free")
    s = Store()
    s.append("org1", Event(agent_id="a", session_id="s3", kind="llm_call", intent="x"))
    _age_session("s3", 45)
    assert anchor.pending_leaves(get_pool(), CFG) == []


def test_already_anchored_through_latest_seq_is_not_pending():
    _mk_org("pro")
    s = Store()
    s.append("org1", Event(agent_id="a", session_id="s4", kind="llm_call", intent="x"))
    _age_session("s4", 45)
    from teluvane import anchor_store
    bid = anchor_store.insert_batch(get_pool(), "0xr", 43113, 1)
    head = anchor.pending_leaves(get_pool(), CFG)[0][3]
    anchor_store.insert_session_anchor(get_pool(), "org1", "s4", 1, bid, head, [])
    assert anchor.pending_leaves(get_pool(), CFG) == []


def test_session_grown_past_its_anchor_is_pending_again():
    _mk_org("pro")
    s = Store()
    s.append("org1", Event(agent_id="a", session_id="s5", kind="llm_call", intent="x"))
    _age_session("s5", 45)
    from teluvane import anchor_store
    bid = anchor_store.insert_batch(get_pool(), "0xr2", 43113, 1)
    anchor_store.insert_session_anchor(get_pool(), "org1", "s5", 1, bid, "aa", [])
    s.append("org1", Event(agent_id="a", session_id="s5", kind="llm_call", intent="y"))
    _age_session("s5", 45)
    leaves = anchor.pending_leaves(get_pool(), CFG)
    assert len(leaves) == 1
    assert leaves[0][2] == 2  # through_seq advanced
```

Note: check the real subscription table/columns first. Run
`grep -rn "org_subscriptions\|def org_plan" teluvane/billing.py migrations/` and
adapt `_mk_org` to whatever `org_plan` actually reads (it may be a
`subscriptions` table with different columns). The test asserting behavior, not
the seeding mechanism, is what matters.

- [ ] **Step 3: Run the test, verify it fails**

Run: `pytest tests/test_anchor_pending.py -v`
Expected: FAIL (`ModuleNotFoundError: teluvane.anchor`)

- [ ] **Step 4: Implement the config + query in `teluvane/anchor.py`**

```python
"""On-chain anchoring of session integrity chains to Avalanche Fuji.

Inert unless the ANCHOR_* env vars are set: chain_config() returns None and every
entry point is a no-op. Never raises into the API request path; RPC and wallet
failures degrade to "not yet anchored" plus a warning log.
"""
import logging
import os
from dataclasses import dataclass

from . import anchor_store
from .billing import org_plan
from .db import get_pool

log = logging.getLogger("teluvane.anchor")


@dataclass
class AnchorConfig:
    rpc_url: str
    contract_address: str
    signer_key: str
    chain_id: int = 43113
    min_session_age_minutes: int = 30
    batch_interval_minutes: int = 10
    confirmations: int = 5
    submit_timeout_minutes: int = 30
    low_balance_alert_avax: float = 0.05
    max_forced_runs_per_org_per_month: int = 20
    forced_run_cooldown_minutes: int = 5
    explorer_tx_url: str = "https://testnet.snowtrace.io/tx/"


def chain_config() -> AnchorConfig | None:
    rpc = os.environ.get("ANCHOR_RPC_URL")
    addr = os.environ.get("ANCHOR_CONTRACT_ADDRESS")
    key = os.environ.get("ANCHOR_SIGNER_PRIVATE_KEY")
    if not (rpc and addr and key):
        return None

    def _int(name, default):
        try:
            return int(os.environ.get(name, default))
        except ValueError:
            return default

    def _float(name, default):
        try:
            return float(os.environ.get(name, default))
        except ValueError:
            return default

    return AnchorConfig(
        rpc_url=rpc, contract_address=addr, signer_key=key,
        chain_id=_int("ANCHOR_CHAIN_ID", 43113),
        min_session_age_minutes=_int("ANCHOR_MIN_SESSION_AGE_MINUTES", 30),
        batch_interval_minutes=_int("ANCHOR_BATCH_INTERVAL_MINUTES", 10),
        confirmations=_int("ANCHOR_CONFIRMATIONS", 5),
        submit_timeout_minutes=_int("ANCHOR_SUBMIT_TIMEOUT_MINUTES", 30),
        low_balance_alert_avax=_float("ANCHOR_LOW_BALANCE_ALERT_AVAX", 0.05),
        explorer_tx_url=os.environ.get("ANCHOR_EXPLORER_TX_URL",
                                      "https://testnet.snowtrace.io/tx/"),
    )


_PENDING_SQL = """
SELECT e.org_id, e.session_id, MAX(e.seq) AS through_seq
FROM events e
GROUP BY e.org_id, e.session_id
HAVING MAX(e.ts) < %s
"""


def pending_leaves(pool, cfg: AnchorConfig):
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc)
              - timedelta(minutes=cfg.min_session_age_minutes)).isoformat()
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(_PENDING_SQL, (cutoff,))
        candidates = cur.fetchall()

    leaves = []
    for org_id, session_id, through_seq in candidates:
        if org_plan(org_id) != "pro":
            continue
        if anchor_store.max_anchored_seq(pool, org_id, session_id) >= through_seq:
            continue
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT hash FROM events WHERE org_id=%s AND session_id=%s "
                        "ORDER BY seq DESC LIMIT 1", (org_id, session_id))
            chain_head = cur.fetchone()[0]
        leaves.append((org_id, session_id, int(through_seq), chain_head))
    return leaves
```

- [ ] **Step 5: Run the test, verify it passes**

Run: `pytest tests/test_anchor_pending.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml teluvane/anchor.py tests/test_anchor_pending.py
git commit -m "feat: anchor config and pending-session query"
```

---

### Task 5: web3 client wrapper + `submit_batch` + balance read

**Files:**
- Create: `teluvane/anchor_chain.py`
- Test: `tests/test_anchor_chain.py`

**Interfaces:**
- Consumes: `AnchorConfig`
- Produces:
  - `anchor_chain.ABI` (list) — the `SessionAnchorRegistry` ABI (anchorBatch, anchoredAt, owner, BatchAnchored)
  - `anchor_chain.make_w3(cfg)` -> a `web3.Web3` bound to `cfg.rpc_url`
  - `anchor_chain.signer_address(cfg) -> str`
  - `anchor_chain.balance_avax(cfg) -> float`
  - `anchor_chain.read_anchored_at(cfg, root_hex: str) -> int` (unix seconds, 0 if not anchored)
  - `anchor_chain.submit_batch(cfg, root_hex: str, session_count: int) -> str` (tx hash hex)
  - `anchor_chain.receipt(cfg, tx_hash: str) -> dict | None` -> `{"block_number": int, "status": int, "gas_used": int, "effective_gas_price": int}` or `None` if not mined
  - `anchor_chain.block_number(cfg) -> int`

- [ ] **Step 1: Write the failing test** (web3 fully mocked, no network)

`tests/test_anchor_chain.py`:

```python
from unittest.mock import MagicMock, patch
from teluvane import anchor_chain
from teluvane.anchor import AnchorConfig

CFG = AnchorConfig(rpc_url="http://rpc", contract_address="0x00000000000000000000000000000000000000aa",
                   signer_key="0x" + "11" * 32)


def _fake_w3():
    w3 = MagicMock()
    w3.eth.get_transaction_count.return_value = 7
    w3.eth.chain_id = 43113
    w3.eth.gas_price = 25_000_000_000
    w3.eth.block_number = 500
    w3.to_wei = lambda v, u: int(v * 1e9)
    w3.from_wei = lambda v, u: v / 1e18
    return w3


def test_submit_batch_signs_and_sends():
    w3 = _fake_w3()
    contract = MagicMock()
    tx = {"from": "0xSigner", "nonce": 7}
    contract.functions.anchorBatch.return_value.build_transaction.return_value = tx
    w3.eth.contract.return_value = contract
    signed = MagicMock(raw_transaction=b"raw")
    w3.eth.account.sign_transaction.return_value = signed
    w3.eth.send_raw_transaction.return_value = bytes.fromhex("ab" * 32)

    with patch.object(anchor_chain, "make_w3", return_value=w3), \
         patch.object(anchor_chain, "signer_address", return_value="0xSigner"):
        txh = anchor_chain.submit_batch(CFG, "0x" + "cd" * 32, 3)
    assert txh == "0x" + "ab" * 32
    contract.functions.anchorBatch.assert_called_once()
    args = contract.functions.anchorBatch.call_args[0]
    assert args[1] == 3


def test_read_anchored_at_returns_zero_when_unanchored():
    w3 = _fake_w3()
    contract = MagicMock()
    contract.functions.anchoredAt.return_value.call.return_value = 0
    w3.eth.contract.return_value = contract
    with patch.object(anchor_chain, "make_w3", return_value=w3):
        assert anchor_chain.read_anchored_at(CFG, "0x" + "00" * 32) == 0


def test_receipt_none_when_not_mined():
    w3 = _fake_w3()
    w3.eth.get_transaction_receipt.side_effect = Exception("not found")
    with patch.object(anchor_chain, "make_w3", return_value=w3):
        assert anchor_chain.receipt(CFG, "0xabc") is None
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `pytest tests/test_anchor_chain.py -v`
Expected: FAIL (`ModuleNotFoundError: teluvane.anchor_chain`)

- [ ] **Step 3: Implement `teluvane/anchor_chain.py`**

```python
"""Thin web3.py wrapper for the SessionAnchorRegistry contract. All calls are
synchronous and single-shot; callers handle retries and error isolation."""
import json
import logging

log = logging.getLogger("teluvane.anchor")

ABI = json.loads("""
[
 {"type":"function","name":"anchorBatch","stateMutability":"nonpayable",
  "inputs":[{"name":"root","type":"bytes32"},{"name":"sessionCount","type":"uint256"}],
  "outputs":[]},
 {"type":"function","name":"anchoredAt","stateMutability":"view",
  "inputs":[{"name":"","type":"bytes32"}],"outputs":[{"name":"","type":"uint256"}]},
 {"type":"function","name":"owner","stateMutability":"view",
  "inputs":[],"outputs":[{"name":"","type":"address"}]},
 {"type":"event","name":"BatchAnchored","anonymous":false,
  "inputs":[{"name":"root","type":"bytes32","indexed":true},
            {"name":"sessionCount","type":"uint256","indexed":false},
            {"name":"timestamp","type":"uint256","indexed":false}]}
]
""")


def make_w3(cfg):
    from web3 import Web3
    return Web3(Web3.HTTPProvider(cfg.rpc_url, request_kwargs={"timeout": 15}))


def _account(cfg):
    from eth_account import Account
    return Account.from_key(cfg.signer_key)


def signer_address(cfg) -> str:
    return _account(cfg).address


def _contract(cfg, w3):
    from web3 import Web3
    return w3.eth.contract(address=Web3.to_checksum_address(cfg.contract_address), abi=ABI)


def balance_avax(cfg) -> float:
    w3 = make_w3(cfg)
    wei = w3.eth.get_balance(signer_address(cfg))
    return w3.from_wei(wei, "ether")


def block_number(cfg) -> int:
    return make_w3(cfg).eth.block_number


def read_anchored_at(cfg, root_hex: str) -> int:
    w3 = make_w3(cfg)
    root = bytes.fromhex(root_hex[2:] if root_hex.startswith("0x") else root_hex)
    return int(_contract(cfg, w3).functions.anchoredAt(root).call())


def submit_batch(cfg, root_hex: str, session_count: int) -> str:
    w3 = make_w3(cfg)
    addr = signer_address(cfg)
    root = bytes.fromhex(root_hex[2:] if root_hex.startswith("0x") else root_hex)
    contract = _contract(cfg, w3)
    nonce = w3.eth.get_transaction_count(addr, "pending")
    max_priority = w3.to_wei(2, "gwei")
    base = w3.eth.gas_price
    tx = contract.functions.anchorBatch(root, session_count).build_transaction({
        "from": addr,
        "nonce": nonce,
        "chainId": cfg.chain_id,
        "gas": 120000,
        "maxPriorityFeePerGas": max_priority,
        "maxFeePerGas": base * 2 + max_priority,
    })
    signed = w3.eth.account.sign_transaction(tx, private_key=cfg.signer_key)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction)
    return "0x" + txh.hex() if not txh.hex().startswith("0x") else txh.hex()


def receipt(cfg, tx_hash: str):
    w3 = make_w3(cfg)
    try:
        r = w3.eth.get_transaction_receipt(tx_hash)
    except Exception:
        return None
    if r is None:
        return None
    return {
        "block_number": int(r["blockNumber"]),
        "status": int(r["status"]),
        "gas_used": int(r["gasUsed"]),
        "effective_gas_price": int(r.get("effectiveGasPrice", 0)),
    }
```

Note: `web3.py` v7 sometimes returns `HexBytes` whose `.hex()` already has `0x`.
The `submit_batch` return line normalizes both; keep the test's expectation
(`"0x" + "ab"*32`) and adjust the normalization if v7 differs on the target
machine.

- [ ] **Step 4: Run the test, verify it passes**

Run: `pytest tests/test_anchor_chain.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add teluvane/anchor_chain.py tests/test_anchor_chain.py
git commit -m "feat: web3 wrapper for SessionAnchorRegistry"
```

---

### Task 6: `run_anchor_pass` with advisory lock and persist-before-submit

**Files:**
- Modify: `teluvane/anchor.py` (add `run_anchor_pass`, `_advisory_lock`)
- Test: `tests/test_anchor_pass.py`

**Interfaces:**
- Consumes: `pending_leaves`, `merkle.build_tree`, `anchor_store.*`, `anchor_chain.submit_batch`
- Produces:
  - `anchor.run_anchor_pass(pool, cfg) -> dict` -> `{"anchored": int, "root": str | None, "tx_hash": str | None, "skipped": str | None}`
  - Advisory lock key constant `anchor.ADVISORY_LOCK_KEY = 0x54454C56` ("TELV")

- [ ] **Step 1: Write the failing test**

`tests/test_anchor_pass.py`:

```python
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from teluvane import anchor, anchor_store
from teluvane.db import get_pool
from teluvane.schema import Event
from teluvane.store import Store

CFG = anchor.AnchorConfig(rpc_url="x", contract_address="0x0", signer_key="0x0")


def _seed_pro_session(session_id, n=1):
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE events, orgs, org_members, anchor_batches, session_anchors "
                    "RESTART IDENTITY CASCADE")
        cur.execute("INSERT INTO orgs(id,name,owner_user_id) VALUES('org1','o','u')")
        conn.commit()
    s = Store()
    for i in range(n):
        s.append("org1", Event(agent_id="a", session_id=session_id, kind="llm_call", intent=str(i)))
    old = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE events SET ts=%s", (old,))
        conn.commit()


def test_run_anchor_pass_persists_then_submits(monkeypatch):
    monkeypatch.setattr(anchor, "org_plan", lambda o: "pro")
    _seed_pro_session("s1", 2)
    with patch.object(anchor.anchor_chain, "submit_batch", return_value="0xtx") as sub:
        res = anchor.run_anchor_pass(get_pool(), CFG)
    assert res["anchored"] == 1
    assert res["tx_hash"] == "0xtx"
    # membership existed before submit was called
    sub.assert_called_once()
    row = anchor_store.latest_anchor(get_pool(), "org1", "s1")
    assert row["status"] == "submitted"
    assert row["anchored_through_seq"] == 2
    assert row["proof"] == []  # single leaf


def test_empty_pending_is_a_noop(monkeypatch):
    monkeypatch.setattr(anchor, "org_plan", lambda o: "pro")
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE events, anchor_batches, session_anchors RESTART IDENTITY CASCADE")
        conn.commit()
    res = anchor.run_anchor_pass(get_pool(), CFG)
    assert res == {"anchored": 0, "root": None, "tx_hash": None, "skipped": "nothing-pending"}


def test_submit_failure_leaves_batch_pending_with_membership(monkeypatch):
    monkeypatch.setattr(anchor, "org_plan", lambda o: "pro")
    _seed_pro_session("s2", 1)
    with patch.object(anchor.anchor_chain, "submit_batch", side_effect=Exception("rpc down")):
        res = anchor.run_anchor_pass(get_pool(), CFG)
    assert res["skipped"] == "submit-failed"
    row = anchor_store.latest_anchor(get_pool(), "org1", "s2")
    assert row["status"] == "pending"          # membership persisted, tx not sent
    assert row["tx_hash"] is None
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `pytest tests/test_anchor_pass.py -v`
Expected: FAIL (`AttributeError: module 'teluvane.anchor' has no attribute 'run_anchor_pass'`)

- [ ] **Step 3: Implement in `teluvane/anchor.py`**

Add the import at top: `from . import anchor_chain, merkle` and:

```python
ADVISORY_LOCK_KEY = 0x54454C56  # "TELV"; scopes run_anchor_pass across web instances


def _try_advisory_lock(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
        return bool(cur.fetchone()[0])


def _advisory_unlock(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))


def run_anchor_pass(pool, cfg: AnchorConfig) -> dict:
    empty = {"anchored": 0, "root": None, "tx_hash": None, "skipped": None}
    lock_conn = pool.getconn() if hasattr(pool, "getconn") else None
    conn = lock_conn or pool.connection().__enter__()
    try:
        if not _try_advisory_lock(conn):
            return {**empty, "skipped": "locked"}
        try:
            leaves = pending_leaves(pool, cfg)
            if not leaves:
                return {**empty, "skipped": "nothing-pending"}

            root, proofs = merkle.build_tree([(o, s, h) for o, s, _seq, h in leaves])
            batch_id = anchor_store.insert_batch(pool, root, cfg.chain_id, len(leaves))
            for org_id, session_id, through_seq, chain_head in leaves:
                anchor_store.insert_session_anchor(
                    pool, org_id, session_id, through_seq, batch_id, chain_head,
                    proofs[(org_id, session_id)])

            try:
                tx_hash = anchor_chain.submit_batch(cfg, root, len(leaves))
            except Exception:
                log.exception("anchor submit failed; batch %s stays pending", batch_id)
                return {"anchored": 0, "root": root, "tx_hash": None,
                        "skipped": "submit-failed"}

            anchor_store.mark_submitted(pool, batch_id, tx_hash)
            log.info("anchor batch submitted root=%s tx=%s sessions=%d",
                     root, tx_hash, len(leaves))
            return {"anchored": len(leaves), "root": root, "tx_hash": tx_hash, "skipped": None}
        finally:
            _advisory_unlock(conn)
    finally:
        if lock_conn is not None:
            pool.putconn(lock_conn)
        else:
            conn.close()
```

Note: verify how `teluvane.db.get_pool()` exposes connections (it is a
`psycopg_pool.ConnectionPool`). If `getconn`/`putconn` are the right names, keep
them; otherwise hold the lock on a `with pool.connection() as conn:` block that
wraps the whole body. The lock and unlock MUST run on the same connection.

- [ ] **Step 4: Run the test, verify it passes**

Run: `pytest tests/test_anchor_pass.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add teluvane/anchor.py tests/test_anchor_pass.py
git commit -m "feat: run_anchor_pass with advisory lock and persist-before-submit"
```

---

### Task 7: `reconcile_pending` (confirmations, timeout, failed cleanup, balance)

**Files:**
- Modify: `teluvane/anchor.py`
- Test: `tests/test_anchor_reconcile.py`

**Interfaces:**
- Consumes: `anchor_store.batches_by_status/update_confirmations/mark_mined/mark_failed`, `anchor_chain.receipt/block_number/balance_avax`
- Produces:
  - `anchor.reconcile_pending(pool, cfg) -> None`

- [ ] **Step 1: Write the failing test**

`tests/test_anchor_reconcile.py`:

```python
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from teluvane import anchor, anchor_store
from teluvane.db import get_pool

CFG = anchor.AnchorConfig(rpc_url="x", contract_address="0x0", signer_key="0x0",
                          confirmations=5, submit_timeout_minutes=30)


def _fresh():
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE anchor_batches, session_anchors RESTART IDENTITY CASCADE")
        conn.commit()


def _submitted_batch(age_minutes=1):
    bid = anchor_store.insert_batch(get_pool(), f"0x{age_minutes:064x}", 43113, 1)
    anchor_store.insert_session_anchor(get_pool(), "o", "s", 1, bid, "aa", [])
    anchor_store.mark_submitted(get_pool(), bid, "0xtx")
    old = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE anchor_batches SET submitted_at=%s WHERE id=%s", (old, bid))
        conn.commit()
    return bid


def test_mined_with_enough_confirmations_marks_mined():
    _fresh()
    bid = _submitted_batch()
    with patch.object(anchor.anchor_chain, "receipt",
                      return_value={"block_number": 100, "status": 1, "gas_used": 90000,
                                    "effective_gas_price": 25_000_000_000}), \
         patch.object(anchor.anchor_chain, "block_number", return_value=110), \
         patch.object(anchor.anchor_chain, "balance_avax", return_value=1.0):
        anchor.reconcile_pending(get_pool(), CFG)
    assert anchor_store.batches_by_status(get_pool(), "mined")[0]["id"] == bid


def test_mined_but_not_enough_confirmations_stays_submitted():
    _fresh()
    _submitted_batch()
    with patch.object(anchor.anchor_chain, "receipt",
                      return_value={"block_number": 100, "status": 1, "gas_used": 1,
                                    "effective_gas_price": 1}), \
         patch.object(anchor.anchor_chain, "block_number", return_value=102), \
         patch.object(anchor.anchor_chain, "balance_avax", return_value=1.0):
        anchor.reconcile_pending(get_pool(), CFG)
    assert anchor_store.batches_by_status(get_pool(), "submitted")
    assert anchor_store.batches_by_status(get_pool(), "submitted")[0]["confirmations"] == 3


def test_reverted_receipt_marks_failed_and_clears_anchors():
    _fresh()
    _submitted_batch()
    with patch.object(anchor.anchor_chain, "receipt",
                      return_value={"block_number": 100, "status": 0, "gas_used": 1,
                                    "effective_gas_price": 1}), \
         patch.object(anchor.anchor_chain, "block_number", return_value=200), \
         patch.object(anchor.anchor_chain, "balance_avax", return_value=1.0):
        anchor.reconcile_pending(get_pool(), CFG)
    assert anchor_store.batches_by_status(get_pool(), "failed")
    assert anchor_store.latest_anchor(get_pool(), "o", "s") is None


def test_timed_out_unmined_batch_marks_failed():
    _fresh()
    _submitted_batch(age_minutes=45)
    with patch.object(anchor.anchor_chain, "receipt", return_value=None), \
         patch.object(anchor.anchor_chain, "block_number", return_value=200), \
         patch.object(anchor.anchor_chain, "balance_avax", return_value=1.0):
        anchor.reconcile_pending(get_pool(), CFG)
    assert anchor_store.batches_by_status(get_pool(), "failed")


def test_low_balance_logs_warning(caplog):
    _fresh()
    with patch.object(anchor.anchor_chain, "balance_avax", return_value=0.001):
        with caplog.at_level("WARNING"):
            anchor.reconcile_pending(get_pool(), CFG)
    assert any("balance" in r.message.lower() for r in caplog.records)
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `pytest tests/test_anchor_reconcile.py -v`
Expected: FAIL (no `reconcile_pending`)

- [ ] **Step 3: Implement in `teluvane/anchor.py`**

```python
def reconcile_pending(pool, cfg: AnchorConfig) -> None:
    try:
        bal = anchor_chain.balance_avax(cfg)
        if bal < cfg.low_balance_alert_avax:
            log.warning("anchor signer balance low: %.4f AVAX (threshold %.4f)",
                        bal, cfg.low_balance_alert_avax)
    except Exception:
        log.exception("anchor balance check failed")

    try:
        head = anchor_chain.block_number(cfg)
    except Exception:
        log.exception("anchor block_number failed; skipping reconcile")
        return

    from datetime import datetime, timezone
    for b in anchor_store.batches_by_status(pool, "pending", "submitted"):
        if b["status"] == "pending" and not b["tx_hash"]:
            # membership persisted but submit never happened; retry it (idempotent on-chain)
            try:
                txh = anchor_chain.submit_batch(cfg, b["root"], b["session_count"])
                anchor_store.mark_submitted(pool, b["id"], txh)
            except Exception:
                log.exception("anchor resubmit failed for batch %s", b["id"])
            continue

        try:
            r = anchor_chain.receipt(cfg, b["tx_hash"])
        except Exception:
            log.exception("anchor receipt fetch failed for batch %s", b["id"])
            continue

        if r is None:
            submitted_at = b["submitted_at"]
            if submitted_at and submitted_at.tzinfo is None:
                submitted_at = submitted_at.replace(tzinfo=timezone.utc)
            age_min = (datetime.now(timezone.utc) - submitted_at).total_seconds() / 60 \
                if submitted_at else 0
            if age_min > cfg.submit_timeout_minutes:
                log.warning("anchor batch %s timed out unmined; marking failed", b["id"])
                anchor_store.mark_failed(pool, b["id"])
            continue

        if r["status"] == 0:
            log.warning("anchor batch %s reverted on chain; marking failed", b["id"])
            anchor_store.mark_failed(pool, b["id"])
            continue

        confirmations = max(0, head - r["block_number"] + 1)
        if confirmations >= cfg.confirmations:
            fee = r["gas_used"] * r["effective_gas_price"]
            anchor_store.mark_mined(pool, b["id"], r["block_number"], r["gas_used"],
                                    fee, confirmations)
            log.info("anchor batch %s mined root=%s block=%d gas=%d",
                     b["id"], b["root"], r["block_number"], r["gas_used"])
        else:
            anchor_store.update_confirmations(pool, b["id"], r["block_number"], confirmations)
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `pytest tests/test_anchor_reconcile.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add teluvane/anchor.py tests/test_anchor_reconcile.py
git commit -m "feat: reconcile_pending with confirmations, timeout, failed cleanup"
```

---

### Task 8: `verify_session` and `anchor_health`

**Files:**
- Modify: `teluvane/anchor.py`
- Test: `tests/test_anchor_verify.py`

**Interfaces:**
- Consumes: `Store.canonical_events`, `Store.events`, `anchor_store.latest_anchor/anchor_for_seq`, `merkle.verify_proof`, `anchor_chain.read_anchored_at/signer_address/balance_avax`
- Produces:
  - `anchor.verify_session(pool, org_id, session_id, through_seq=None) -> dict` with keys: `anchored`, `org_id`, `proof`, `through_seq`, `total_seq`, `root`, `tx_hash`, `block_number`, `confirmations`, `mined_at`, `onchain_ts`, `head_stored`, `head_recomputed`, `head_matches`, `proof_ok`, `rpc_ok`, `status` (`org_id` and `proof` are echoed so the browser panel can recompute the root itself)
  - `anchor.anchor_health(pool) -> dict` with keys: `enabled`, `signer_address`, `signer_balance_avax`, `low_balance`, `rpc_ok`, `pending_batches`, `last_batch_at`, `last_batch_tx`, `chain_id`

- [ ] **Step 1: Write the failing test**

`tests/test_anchor_verify.py`:

```python
from unittest.mock import patch
from teluvane import anchor, anchor_store, merkle
from teluvane.db import get_pool
from teluvane.schema import Event
from teluvane.store import Store

CFG = anchor.AnchorConfig(rpc_url="x", contract_address="0x0", signer_key="0x0")


def _seed():
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE events, orgs, anchor_batches, session_anchors RESTART IDENTITY CASCADE")
        cur.execute("INSERT INTO orgs(id,name,owner_user_id) VALUES('org1','o','u')")
        conn.commit()
    s = Store()
    for i in range(3):
        s.append("org1", Event(agent_id="a", session_id="s1", kind="llm_call", intent=str(i)))
    head = s.events("org1", "s1")[-1].hash
    root, proofs = merkle.build_tree([("org1", "s1", head)])
    bid = anchor_store.insert_batch(get_pool(), root, 43113, 1)
    anchor_store.insert_session_anchor(get_pool(), "org1", "s1", 3, bid, head, proofs[("org1", "s1")])
    anchor_store.mark_submitted(get_pool(), bid, "0xtx")
    anchor_store.mark_mined(get_pool(), bid, 42, 90000, 1, 6)
    return root, head


def test_verify_session_ok_when_root_on_chain():
    root, head = _seed()
    with patch.object(anchor.anchor_chain, "read_anchored_at", return_value=1_700_000_000):
        res = anchor.verify_session(get_pool(), "org1", "s1", cfg=CFG)
    assert res["anchored"] and res["head_matches"] and res["proof_ok"]
    assert res["status"] == "verified"
    assert res["onchain_ts"] == 1_700_000_000


def test_verify_session_mismatch_when_root_absent_on_chain():
    _seed()
    with patch.object(anchor.anchor_chain, "read_anchored_at", return_value=0):
        res = anchor.verify_session(get_pool(), "org1", "s1", cfg=CFG)
    assert res["status"] == "mismatch"


def test_verify_session_rpc_error_is_reported_not_raised():
    _seed()
    with patch.object(anchor.anchor_chain, "read_anchored_at", side_effect=Exception("rpc")):
        res = anchor.verify_session(get_pool(), "org1", "s1", cfg=CFG)
    assert res["rpc_ok"] is False and res["status"] == "rpc-unreachable"


def test_verify_session_not_anchored():
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE events, orgs, anchor_batches, session_anchors RESTART IDENTITY CASCADE")
        cur.execute("INSERT INTO orgs(id,name,owner_user_id) VALUES('org1','o','u')")
        conn.commit()
    Store().append("org1", Event(agent_id="a", session_id="s9", kind="llm_call", intent="x"))
    res = anchor.verify_session(get_pool(), "org1", "s9", cfg=CFG)
    assert res["anchored"] is False and res["status"] == "not-anchored"
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `pytest tests/test_anchor_verify.py -v`
Expected: FAIL (no `verify_session`)

- [ ] **Step 3: Implement in `teluvane/anchor.py`**

```python
def verify_session(pool, org_id: str, session_id: str, through_seq: int | None = None,
                   cfg: AnchorConfig | None = None) -> dict:
    cfg = cfg or chain_config()
    from .store import Store
    store = Store(pool)
    events = store.events(org_id, session_id)
    total_seq = events[-1].seq if events else 0

    row = (anchor_store.anchor_for_seq(pool, org_id, session_id, through_seq)
           if through_seq else anchor_store.latest_anchor(pool, org_id, session_id))
    base = {"anchored": False, "through_seq": None, "total_seq": total_seq,
            "root": None, "tx_hash": None, "block_number": None, "confirmations": 0,
            "mined_at": None, "onchain_ts": None, "head_stored": None,
            "head_recomputed": None, "head_matches": False, "proof_ok": False,
            "rpc_ok": True, "status": "not-anchored"}
    if not row:
        return base

    canon = store.canonical_events(org_id, session_id)
    upto = [c for c in canon if c["seq"] <= row["anchored_through_seq"]]
    head_recomputed = upto[-1]["hash"] if upto else None
    proof_ok = merkle.verify_proof(org_id, session_id, row["chain_head"],
                                   row["proof"], row["batch_root_or_none"]) \
        if False else None  # replaced below

    # recompute the batch root from this leaf + proof, compare to on-chain
    from .merkle import verify_proof, leaf_hash
    # derive the root the proof implies:
    acc = leaf_hash(org_id, session_id, row["chain_head"])
    from .merkle import _node
    for sib_hex in row["proof"]:
        acc = _node(acc, bytes.fromhex(sib_hex[2:]))
    implied_root = "0x" + acc.hex()

    out = {**base,
           "anchored": True,
           "through_seq": row["anchored_through_seq"],
           "root": implied_root,
           "tx_hash": row["tx_hash"],
           "block_number": row["block_number"],
           "confirmations": row["confirmations"],
           "mined_at": row["mined_at"].isoformat() if row["mined_at"] else None,
           "head_stored": row["chain_head"],
           "head_recomputed": head_recomputed,
           "head_matches": head_recomputed == row["chain_head"],
           "proof_ok": True}

    if not cfg:
        out["status"] = "no-config"
        return out
    try:
        ts = anchor_chain.read_anchored_at(cfg, implied_root)
    except Exception:
        log.exception("anchor verify RPC read failed")
        out["rpc_ok"] = False
        out["status"] = "rpc-unreachable"
        return out
    out["onchain_ts"] = ts or None
    if ts and out["head_matches"]:
        out["status"] = "verified"
    elif row["status"] == "submitted":
        out["status"] = "pending"
    else:
        out["status"] = "mismatch"
    return out


def anchor_health(pool) -> dict:
    cfg = chain_config()
    if not cfg:
        return {"enabled": False}
    h = {"enabled": True, "chain_id": cfg.chain_id, "rpc_ok": True,
         "signer_address": None, "signer_balance_avax": None, "low_balance": False,
         "pending_batches": len(anchor_store.batches_by_status(pool, "pending", "submitted")),
         "last_batch_at": None, "last_batch_tx": None}
    try:
        h["signer_address"] = anchor_chain.signer_address(cfg)
        bal = anchor_chain.balance_avax(cfg)
        h["signer_balance_avax"] = round(bal, 5)
        h["low_balance"] = bal < cfg.low_balance_alert_avax
    except Exception:
        h["rpc_ok"] = False
    mined = anchor_store.batches_by_status(pool, "mined")
    if mined:
        last = mined[-1]
        h["last_batch_at"] = last["mined_at"].isoformat() if last["mined_at"] else None
        h["last_batch_tx"] = last["tx_hash"]
    return h
```

Clean up the dead `proof_ok`/`base["batch_root_or_none"]` scaffolding while
implementing; the test only checks the documented keys. Expose `_node` from
`merkle.py` (it already exists as a module function) or add a public
`root_from_proof(org_id, session_id, head, proof) -> str` helper to `merkle.py`
and use that instead of reaching into `_node`. Prefer the helper; add its own
unit test in `tests/test_merkle.py`.

- [ ] **Step 4: Run the test, verify it passes**

Run: `pytest tests/test_anchor_verify.py tests/test_merkle.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add teluvane/anchor.py teluvane/merkle.py tests/test_anchor_verify.py tests/test_merkle.py
git commit -m "feat: verify_session and anchor_health"
```

---

### Task 9: Scheduler integration

**Files:**
- Modify: `teluvane/scheduler.py`
- Test: `tests/test_scheduler_anchor.py`

**Interfaces:**
- Consumes: `anchor.chain_config`, `anchor.reconcile_pending`, `anchor.run_anchor_pass`
- Produces: `scheduler._anchor_due(interval_minutes: int) -> bool`; a call to the anchor steps inside the existing tick function

- [ ] **Step 1: Read the current tick**

Run: `grep -n "run_due_schedules\|_scheduler_loop\|def tick\|TICK_INTERVAL" teluvane/scheduler.py teluvane/ingest.py`
Identify the function the 60s loop calls (referred to below as `tick()`).

- [ ] **Step 2: Write the failing test**

`tests/test_scheduler_anchor.py`:

```python
from unittest.mock import patch
from teluvane import scheduler, anchor


def test_tick_runs_anchor_when_configured():
    cfg = anchor.AnchorConfig(rpc_url="x", contract_address="0x0", signer_key="0x0")
    with patch.object(scheduler.anchor, "chain_config", return_value=cfg), \
         patch.object(scheduler.anchor, "reconcile_pending") as recon, \
         patch.object(scheduler.anchor, "run_anchor_pass") as run, \
         patch.object(scheduler, "_anchor_due", return_value=True):
        scheduler.run_due_schedules()   # or whatever tick() is named
    recon.assert_called_once()
    run.assert_called_once()


def test_tick_skips_anchor_when_not_configured():
    with patch.object(scheduler.anchor, "chain_config", return_value=None), \
         patch.object(scheduler.anchor, "reconcile_pending") as recon:
        scheduler.run_due_schedules()
    recon.assert_not_called()
```

- [ ] **Step 3: Run the test, verify it fails**

Run: `pytest tests/test_scheduler_anchor.py -v`
Expected: FAIL (`AttributeError` on `scheduler.anchor` or `_anchor_due`)

- [ ] **Step 4: Implement**

At the top of `teluvane/scheduler.py`: `from . import anchor`.

Add:

```python
_last_anchor_run = None


def _anchor_due(interval_minutes: int) -> bool:
    global _last_anchor_run
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if _last_anchor_run is None or (now - _last_anchor_run).total_seconds() >= interval_minutes * 60:
        _last_anchor_run = now
        return True
    return False
```

Inside `tick()` (the function the loop calls), after the tribunal/schedule work:

```python
    cfg = anchor.chain_config()
    if cfg:
        try:
            anchor.reconcile_pending(get_pool(), cfg)
            if _anchor_due(cfg.batch_interval_minutes):
                anchor.run_anchor_pass(get_pool(), cfg)
        except Exception:
            logging.getLogger("teluvane.anchor").exception("anchor tick failed")
```

(`get_pool` is already imported in `scheduler.py`.)

- [ ] **Step 5: Run the test, verify it passes**

Run: `pytest tests/test_scheduler_anchor.py tests/test_scheduler.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add teluvane/scheduler.py tests/test_scheduler_anchor.py
git commit -m "feat: run anchoring from the scheduler tick"
```

---

### Task 10: API routes + `/sessions` anchor field + forced-run limits

**Files:**
- Modify: `teluvane/ingest.py`
- Modify: `teluvane/store.py` (`sessions()` gains an `anchor` field per row)
- Create: `teluvane/anchor_forced.py` (cooldown + monthly cap bookkeeping, in-memory + DB-backed count)
- Test: `tests/test_anchor_api.py`

**Interfaces:**
- Consumes: `anchor.verify_session`, `anchor.anchor_health`, `anchor.run_anchor_pass`, `anchor.chain_config`, `anchor_store.set_public/is_public`, `Store.canonical_events`
- Produces these routes (all JSON unless noted):
  - `GET /anchor/{session_id}` (auth `current_org`) -> `verify_session(...)` dict
  - `GET /anchor/{session_id}/canonical` (auth `current_org`) -> `Store.canonical_events` list
  - `GET /anchor/contract` (auth `current_org`) -> `{chain_id, contract_address, explorer_tx_url, rpc_url}`
  - `GET /anchor/status` (auth `current_org`) -> `anchor_health(pool)`
  - `POST /anchor/run` (auth `current_org`, Pro, owner role) -> `{"anchored": int, ...}` or 429 on cooldown / cap
  - `PUT /anchor/{session_id}/public` (auth `current_org`, body `{public: bool}`) -> `{"public": bool}`
  - `GET /verify/public/{session_id}` (NO auth) -> `{canonical, proof, root, tx_hash, chain_id, contract_address, explorer_tx_url, rpc_url, ...}` or 404 when not public

- [ ] **Step 1: Write the failing test**

`tests/test_anchor_api.py`:

```python
from fastapi.testclient import TestClient
from unittest.mock import patch
from teluvane.ingest import app
from teluvane import anchor
from teluvane.db import get_pool

client = TestClient(app)
CFG = anchor.AnchorConfig(rpc_url="http://rpc", contract_address="0xC0FFEE",
                          signer_key="0x0", explorer_tx_url="https://x/tx/")


def _auth(make_jwt):
    # follow the pattern in tests/test_api.py for creating an org + JWT
    ...


def test_anchor_contract_route(make_jwt):
    headers = _auth(make_jwt)
    with patch.object(anchor, "chain_config", return_value=CFG):
        r = client.get("/anchor/contract", headers=headers)
    assert r.status_code == 200
    assert r.json()["contract_address"] == "0xC0FFEE"
    assert r.json()["chain_id"] == 43113


def test_public_verify_404_when_not_opted_in(make_jwt):
    r = client.get("/verify/public/never-made-public")
    assert r.status_code == 404


def test_public_verify_returns_bundle_after_opt_in(make_jwt):
    headers = _auth(make_jwt)
    # seed an anchored session for this org named "s1" (reuse helper from test_anchor_verify)
    ...
    client.put("/anchor/s1/public", headers=headers, json={"public": True})
    with patch.object(anchor, "chain_config", return_value=CFG), \
         patch.object(anchor.anchor_chain, "read_anchored_at", return_value=1_700_000_000):
        r = client.get("/verify/public/s1")
    assert r.status_code == 200
    body = r.json()
    assert body["contract_address"] == "0xC0FFEE"
    assert isinstance(body["canonical"], list)
    assert "proof" in body


def test_forced_run_cooldown(make_jwt):
    headers = _auth(make_jwt)   # must be Pro + owner
    with patch.object(anchor, "chain_config", return_value=CFG), \
         patch.object(anchor, "run_anchor_pass", return_value={"anchored": 0, "root": None,
                                                               "tx_hash": None, "skipped": "nothing-pending"}):
        r1 = client.post("/anchor/run", headers=headers)
        r2 = client.post("/anchor/run", headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 429
```

Fill the `_auth` and seeding helpers by copying the org+JWT setup already used in
`tests/test_api.py` and the anchored-session seeding from
`tests/test_anchor_verify.py`.

- [ ] **Step 2: Run the test, verify it fails**

Run: `pytest tests/test_anchor_api.py -v`
Expected: FAIL (routes 404)

- [ ] **Step 3: Implement `teluvane/anchor_forced.py`**

```python
"""Cooldown + monthly cap for the manual POST /anchor/run trigger, so a Pro org
cannot burn the shared signer wallet by spamming forced anchor passes."""
import time
from datetime import datetime, timezone

_last_run: dict[str, float] = {}
_month_count: dict[tuple[str, str], int] = {}


def _month_key(org_id: str) -> tuple[str, str]:
    return (org_id, datetime.now(timezone.utc).strftime("%Y-%m"))


def check_and_record(org_id: str, cooldown_minutes: int, monthly_cap: int) -> str | None:
    now = time.time()
    last = _last_run.get(org_id, 0)
    if now - last < cooldown_minutes * 60:
        return "cooldown"
    key = _month_key(org_id)
    if _month_count.get(key, 0) >= monthly_cap:
        return "monthly-cap"
    _last_run[org_id] = now
    _month_count[key] = _month_count.get(key, 0) + 1
    return None
```

- [ ] **Step 4: Add `anchor` field to `Store.sessions`**

In `store.py`, after building the session rows, left-join the latest anchor
status. Simplest: after fetching rows, for each `session_id` call a batched query:

```python
        ids = [r["session_id"] for r in rows]
        anchor_status = {}
        if ids:
            with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT sa.session_id, b.status FROM session_anchors sa "
                    "JOIN anchor_batches b ON b.id = sa.batch_id "
                    "WHERE sa.org_id=%s AND sa.session_id = ANY(%s) "
                    "ORDER BY sa.anchored_through_seq DESC", (org_id, ids))
                for row in cur.fetchall():
                    anchor_status.setdefault(row["session_id"], row["status"])
        for r in rows:
            r["anchor"] = anchor_status.get(r["session_id"], "none")
```

Update `tests/test_store.py` if it asserts the exact session-row shape.

- [ ] **Step 5: Add the routes to `ingest.py`**

```python
from . import anchor, anchor_store, anchor_forced

@app.get("/anchor/contract")
def anchor_contract(org_id: str = Depends(current_org)) -> dict:
    cfg = anchor.chain_config()
    if not cfg:
        raise HTTPException(status_code=404, detail="anchoring not configured")
    return {"chain_id": cfg.chain_id, "contract_address": cfg.contract_address,
            "explorer_tx_url": cfg.explorer_tx_url, "rpc_url": cfg.rpc_url}

@app.get("/anchor/status")
def anchor_status_ep(org_id: str = Depends(current_org)) -> dict:
    return anchor.anchor_health(store.pool)

@app.get("/anchor/{session_id}")
def anchor_session_ep(session_id: str, org_id: str = Depends(current_org)) -> dict:
    return anchor.verify_session(store.pool, org_id, session_id)

@app.get("/anchor/{session_id}/canonical")
def anchor_canonical_ep(session_id: str, org_id: str = Depends(current_org)) -> list[dict]:
    return store.canonical_events(org_id, session_id)

@app.put("/anchor/{session_id}/public")
def anchor_public_ep(session_id: str, public: bool = Body(embed=True),
                     org_id: str = Depends(current_org)) -> dict:
    anchor_store.set_public(store.pool, org_id, session_id, public)
    return {"public": public}

@app.post("/anchor/run")
@limiter.limit(AUDIT_RATE_LIMIT)
def anchor_run_ep(request: Request, org_id: str = Depends(current_org)) -> dict:
    if org_plan(org_id) != "pro":
        raise HTTPException(status_code=403, detail="Pro plan required")
    cfg = anchor.chain_config()
    if not cfg:
        raise HTTPException(status_code=404, detail="anchoring not configured")
    reason = anchor_forced.check_and_record(
        org_id, cfg.forced_run_cooldown_minutes, cfg.max_forced_runs_per_org_per_month)
    if reason:
        raise HTTPException(status_code=429, detail=f"forced anchor blocked: {reason}")
    return anchor.run_anchor_pass(store.pool, cfg)

@app.get("/verify/public/{session_id}")
def verify_public_ep(session_id: str) -> dict:
    # unauthenticated: find which org made this session public
    with store.pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT org_id FROM session_anchor_public WHERE session_id=%s", (session_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    org_id = row[0]
    v = anchor.verify_session(store.pool, org_id, session_id)
    if not v["anchored"]:
        raise HTTPException(status_code=404, detail="not anchored")
    canonical = store.canonical_events(org_id, session_id)
    latest = anchor_store.latest_anchor(store.pool, org_id, session_id)
    cfg = anchor.chain_config()
    return {"session_id": session_id, "canonical": canonical, "proof": latest["proof"],
            "chain_head": latest["chain_head"], "through_seq": latest["anchored_through_seq"],
            "root": v["root"], "tx_hash": v["tx_hash"], "verify": v,
            "chain_id": cfg.chain_id if cfg else None,
            "contract_address": cfg.contract_address if cfg else None,
            "explorer_tx_url": cfg.explorer_tx_url if cfg else None,
            "rpc_url": cfg.rpc_url if cfg else None}
```

Route ordering: FastAPI matches in definition order, so define `/anchor/contract`,
`/anchor/status` BEFORE `/anchor/{session_id}` (a literal path vs a path param).
Put the static ones first as written above.

CORS: `/verify/public/*` must be reachable from the browser with no auth header.
Check the existing `CORSMiddleware` config allows GET from the frontend origin
(it already does for the dashboard); no change expected, but confirm in
`tests/test_cors.py` style.

- [ ] **Step 6: Run the test, verify it passes**

Run: `pytest tests/test_anchor_api.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Full suite**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add teluvane/ingest.py teluvane/store.py teluvane/anchor_forced.py tests/test_anchor_api.py tests/test_store.py
git commit -m "feat: anchor API routes, public verify endpoint, session anchor status"
```

---

### Task 11: Evidence pack on-chain section

**Files:**
- Modify: `teluvane/evidence.py`
- Modify: `teluvane/ingest.py` (`/evidence/{session_id}` passes anchor data in)
- Test: `tests/test_evidence.py` (add cases)

**Interfaces:**
- Consumes: `anchor.verify_session`, `anchor_store.latest_anchor`
- Produces: `build_evidence_pack(..., anchor: dict | None = None)` and `build_evidence_pdf(..., anchor=None)`; the HTML gains an "On-chain anchor" section and a privacy line.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_evidence.py`:

```python
def test_evidence_pack_without_anchor_says_not_anchored():
    pack = build_evidence_pack("s1", [], [], "eu_ai_act", True, anchor=None)
    assert "not anchored" in pack["html"].lower()

def test_evidence_pack_with_anchor_shows_tx_and_privacy_line():
    a = {"anchored": True, "status": "verified", "root": "0xabc", "tx_hash": "0xdef",
         "block_number": 42, "through_seq": 3, "total_seq": 3, "onchain_ts": 1700000000,
         "explorer_tx_url": "https://testnet.snowtrace.io/tx/"}
    pack = build_evidence_pack("s1", [], [], "eu_ai_act", True, anchor=a)
    html = pack["html"]
    assert "https://testnet.snowtrace.io/tx/0xdef" in html
    assert "0xabc" in html
    assert "only hashes" in html.lower()
    assert pack["json"]["anchor"]["tx_hash"] == "0xdef"
```

- [ ] **Step 2: Run, verify it fails**

Run: `pytest tests/test_evidence.py -v`
Expected: FAIL (`build_evidence_pack() got an unexpected keyword argument 'anchor'`)

- [ ] **Step 3: Implement**

Change the signatures to accept `anchor: dict | None = None`. In `build_evidence_pack`,
add `"anchor": anchor` to the `js` dict. In `_render_html`, add before the
violations section:

```python
    if anchor and anchor.get("anchored"):
        tx = anchor.get("tx_hash") or ""
        url = (anchor.get("explorer_tx_url") or "") + tx
        anchor_html = (
            "<h2>On-chain anchor</h2><p>"
            f"<b>Status:</b> {_html.escape(anchor.get('status',''))}<br>"
            f"<b>Merkle root:</b> <code>{_html.escape(anchor.get('root',''))}</code><br>"
            f"<b>Avalanche Fuji tx:</b> <a href=\"{_html.escape(url)}\">{_html.escape(tx)}</a><br>"
            f"<b>Block:</b> {anchor.get('block_number')}<br>"
            f"<b>Anchored through event:</b> {anchor.get('through_seq')} of {anchor.get('total_seq')}</p>"
            "<p><b>Chain of custody:</b> SHA-256 event chain (through event "
            f"{anchor.get('through_seq')} of {anchor.get('total_seq')}) to Merkle root to "
            f"Avalanche Fuji tx {_html.escape(tx)} at block {anchor.get('block_number')}.</p>"
            "<p><b>Privacy:</b> Only hashes and a batch count are written on chain. "
            "No event content, tool arguments, model output, or personal data leaves TELUVANE.</p>")
    else:
        anchor_html = ("<h2>On-chain anchor</h2><p>This session is not anchored on "
                       "Avalanche. The SHA-256 event chain above is still tamper-evident "
                       "within TELUVANE.</p>")
```

Insert `{anchor_html}` into the returned HTML between the header `<p>` block and
`<h2>Violations</h2>`. Add the `anchor` parameter to `_render_html`'s signature
and the `build_evidence_pdf` passthrough.

In `ingest.py`, the `/evidence/{session_id}` and `/evidence/{session_id}/pdf`
handlers: build `anchor` via `anchor.verify_session(store.pool, org_id, session_id)`
and merge in `explorer_tx_url` from `anchor.chain_config()`; pass `anchor=...`.
Wrap in `try/except` so a broken RPC never breaks evidence export (pass `anchor=None`).

- [ ] **Step 4: Run, verify it passes**

Run: `pytest tests/test_evidence.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add teluvane/evidence.py teluvane/ingest.py tests/test_evidence.py
git commit -m "feat: on-chain anchor section in evidence pack"
```

---

### Task 12: Solidity contract + Foundry tests + CI job

**Files:**
- Create: `contracts/SessionAnchorRegistry.sol`
- Create: `contracts/test/SessionAnchorRegistry.t.sol`
- Create: `contracts/foundry.toml`
- Modify: `.github/workflows/ci.yml` (add a `contracts` job)

**Interfaces:**
- Produces: the deployed ABI used by `teluvane/anchor_chain.py::ABI` and `frontend/lib` (keep them in sync by hand; both are tiny).

- [ ] **Step 1: Write the contract**

`contracts/SessionAnchorRegistry.sol` (exact code from spec §1).

- [ ] **Step 2: Write the Foundry test**

`contracts/test/SessionAnchorRegistry.t.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {SessionAnchorRegistry} from "../SessionAnchorRegistry.sol";

contract SessionAnchorRegistryTest is Test {
    SessionAnchorRegistry reg;
    address owner = address(this);
    address stranger = address(0xBEEF);

    function setUp() public { reg = new SessionAnchorRegistry(); }

    function test_anchor_sets_timestamp_and_emits() public {
        bytes32 root = keccak256("r1");
        vm.expectEmit(true, false, false, true);
        emit SessionAnchorRegistry.BatchAnchored(root, 3, block.timestamp);
        reg.anchorBatch(root, 3);
        assertEq(reg.anchoredAt(root), block.timestamp);
    }

    function test_non_owner_reverts() public {
        vm.prank(stranger);
        vm.expectRevert(SessionAnchorRegistry.NotOwner.selector);
        reg.anchorBatch(keccak256("r"), 1);
    }

    function test_double_anchor_reverts() public {
        bytes32 root = keccak256("r2");
        reg.anchorBatch(root, 1);
        vm.expectRevert(SessionAnchorRegistry.AlreadyAnchored.selector);
        reg.anchorBatch(root, 1);
    }

    function test_empty_batch_reverts() public {
        vm.expectRevert(SessionAnchorRegistry.EmptyBatch.selector);
        reg.anchorBatch(keccak256("r3"), 0);
    }
}
```

`contracts/foundry.toml`:

```toml
[profile.default]
src = "."
test = "test"
out = "out"
libs = ["lib"]
solc = "0.8.24"
```

- [ ] **Step 3: Run locally**

Run: `cd contracts && forge install foundry-rs/forge-std --no-git && forge test -vvv`
Expected: PASS (4 tests). If `forge` is not installed:
`curl -L https://foundry.paradigm.xyz | bash && foundryup`.

- [ ] **Step 4: Add the CI job**

In `.github/workflows/ci.yml`, add:

```yaml
  contracts:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: contracts } }
    steps:
      - uses: actions/checkout@v4
      - uses: foundry-rs/foundry-toolchain@v1
      - run: forge install foundry-rs/forge-std --no-git
      - run: forge test -vvv
```

- [ ] **Step 5: Commit**

```bash
git add contracts/ .github/workflows/ci.yml
git commit -m "feat: SessionAnchorRegistry contract with Foundry tests"
```

---

### Task 13: Deploy script + smoke script + DEPLOY.md

**Files:**
- Create: `scripts/deploy_anchor.py`
- Create: `scripts/anchor_smoke.py`
- Modify: `DEPLOY.md`
- Modify: `frontend/.env.local.example`
- Create/Modify: root `.env.example` (if present) or document in DEPLOY.md

**Interfaces:** none consumed by app code; operator tooling only.

- [ ] **Step 1: Write `scripts/deploy_anchor.py`**

```python
"""Compile and deploy SessionAnchorRegistry to the chain in ANCHOR_RPC_URL,
signed by ANCHOR_SIGNER_PRIVATE_KEY. Prints the deployed address.

  python scripts/deploy_anchor.py
"""
import os
import sys
from pathlib import Path

from solcx import compile_standard, install_solc
from web3 import Web3
from eth_account import Account

SOL = Path("contracts/SessionAnchorRegistry.sol")


def main() -> int:
    rpc = os.environ["ANCHOR_RPC_URL"]
    key = os.environ["ANCHOR_SIGNER_PRIVATE_KEY"]
    install_solc("0.8.24")
    compiled = compile_standard({
        "language": "Solidity",
        "sources": {SOL.name: {"content": SOL.read_text()}},
        "settings": {"outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}}},
    }, solc_version="0.8.24")
    c = compiled["contracts"][SOL.name]["SessionAnchorRegistry"]
    abi, bytecode = c["abi"], c["evm"]["bytecode"]["object"]

    w3 = Web3(Web3.HTTPProvider(rpc))
    acct = Account.from_key(key)
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx = Contract.constructor().build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gas": 500000,
        "maxPriorityFeePerGas": w3.to_wei(2, "gwei"),
        "maxFeePerGas": w3.eth.gas_price * 2 + w3.to_wei(2, "gwei"),
        "chainId": int(os.environ.get("ANCHOR_CHAIN_ID", "43113")),
    })
    signed = w3.eth.account.sign_transaction(tx, private_key=key)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction)
    print("deploy tx:", txh.hex())
    rcpt = w3.eth.wait_for_transaction_receipt(txh)
    print("ANCHOR_CONTRACT_ADDRESS=" + rcpt["contractAddress"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write `scripts/anchor_smoke.py`**

```python
"""Manual Fuji integration check. NOT run in CI. Requires ANCHOR_* env + funded
signer. Anchors a throwaway batch and reads it back.

  python scripts/anchor_smoke.py
"""
import sys
from teluvane import anchor, anchor_chain, merkle


def main() -> int:
    cfg = anchor.chain_config()
    assert cfg, "ANCHOR_* env not set"
    print("signer:", anchor_chain.signer_address(cfg),
          "balance:", anchor_chain.balance_avax(cfg), "AVAX")
    root, _ = merkle.build_tree([("smoke-org", "smoke-session", "ab" * 32)])
    print("root:", root)
    tx = anchor_chain.submit_batch(cfg, root, 1)
    print("tx:", tx)
    import time
    for _ in range(30):
        r = anchor_chain.receipt(cfg, tx)
        if r:
            print("mined block", r["block_number"], "status", r["status"])
            break
        time.sleep(5)
    ts = anchor_chain.read_anchored_at(cfg, root)
    print("anchoredAt:", ts)
    assert ts > 0, "root not found on chain after mining"
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Update `DEPLOY.md`**

Add an "On-chain anchoring (Avalanche Fuji)" section:
- Generate a hot wallet: `python -c "from eth_account import Account; a=Account.create(); print(a.address, a.key.hex())"`.
- Fund it from `https://faucet.avax.network/` (Fuji C-Chain).
- `pip install -e ".[dev]"` then `ANCHOR_RPC_URL=... ANCHOR_SIGNER_PRIVATE_KEY=... python scripts/deploy_anchor.py`.
- Set backend env: `ANCHOR_RPC_URL`, `ANCHOR_CONTRACT_ADDRESS`, `ANCHOR_SIGNER_PRIVATE_KEY`, and the optional tuning vars from the spec §7.
- Set frontend env: `NEXT_PUBLIC_ANCHOR_CONTRACT_ADDRESS`, `NEXT_PUBLIC_ANCHOR_RPC_URL` (optional), `NEXT_PUBLIC_ANCHOR_EXPLORER_TX_URL`.
- Rotation: redeploy the contract, repoint `ANCHOR_CONTRACT_ADDRESS`; old anchors stay valid on the old address.
- Note the hot wallet holds only small amounts of test AVAX; the low-balance warning fires below `ANCHOR_LOW_BALANCE_ALERT_AVAX`.

- [ ] **Step 4: Update `frontend/.env.local.example`**

Add:
```
NEXT_PUBLIC_ANCHOR_CONTRACT_ADDRESS=
NEXT_PUBLIC_ANCHOR_RPC_URL=
NEXT_PUBLIC_ANCHOR_EXPLORER_TX_URL=https://testnet.snowtrace.io/tx/
```

- [ ] **Step 5: Commit**

```bash
git add scripts/deploy_anchor.py scripts/anchor_smoke.py DEPLOY.md frontend/.env.local.example
git commit -m "chore: anchor deploy + smoke scripts and deploy docs"
```

---

### Task 14: Frontend Merkle + chain verify libs with shared vectors

**Files:**
- Create: `frontend/lib/merkle.ts`
- Create: `frontend/lib/chainVerify.ts`
- Create: `frontend/lib/anchorVectors.test.ts`
- Copy: `tests/fixtures/merkle_vectors.json` -> `frontend/lib/__fixtures__/merkle_vectors.json`; `tests/fixtures/chain_vectors.json` -> `frontend/lib/__fixtures__/chain_vectors.json`

**Interfaces:**
- Produces:
  - `merkle.leafHash(orgId: string, sessionId: string, chainHeadHex: string): Promise<Uint8Array>`
  - `merkle.rootFromProof(orgId, sessionId, chainHeadHex, proof: string[]): Promise<string>` (returns `"0x"`-prefixed)
  - `merkle.LEAF_PREFIX`, `merkle.NODE_PREFIX` (Uint8Array)
  - `chainVerify.verifyChain(events: {seq:number; prev_hash:string; hash:string; canonical:string}[]): Promise<{ok: boolean; failAt?: number; head?: string}>`

- [ ] **Step 1: Add the fixture copy step to the build**

Add an npm script to `frontend/package.json`: `"sync-vectors": "node scripts/sync-vectors.mjs"`, and `frontend/scripts/sync-vectors.mjs` that copies the two JSON files from `../tests/fixtures/`. Run it now to seed `frontend/lib/__fixtures__/`.

- [ ] **Step 2: Write the failing test**

`frontend/lib/anchorVectors.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import merkleVectors from "./__fixtures__/merkle_vectors.json";
import chainVectors from "./__fixtures__/chain_vectors.json";
import { rootFromProof } from "./merkle";
import { verifyChain } from "./chainVerify";

describe("merkle parity with Python", () => {
  for (const [i, c] of merkleVectors.cases.entries()) {
    it(`case ${i} roots match`, async () => {
      for (let j = 0; j < c.leaves.length; j++) {
        const l = c.leaves[j];
        const r = await rootFromProof(l.org_id, l.session_id, l.chain_head, c.proofs[j]);
        expect(r).toBe(c.root);
      }
    });
  }
});

describe("chain verify parity with Python", () => {
  it("verifies the recorded chain", async () => {
    const res = await verifyChain(chainVectors.events);
    expect(res.ok).toBe(true);
    expect(res.head).toBe(chainVectors.events.at(-1).hash);
  });
  it("flags a tampered canonical string", async () => {
    const evts = chainVectors.events.map((e: any) => ({ ...e }));
    evts[0] = { ...evts[0], canonical: evts[0].canonical.replace(/}$/, ' }') };
    const res = await verifyChain(evts);
    expect(res.ok).toBe(false);
    expect(res.failAt).toBe(evts[0].seq);
  });
});
```

- [ ] **Step 3: Run, verify it fails**

Run: `cd frontend && npx vitest run lib/anchorVectors.test.ts`
Expected: FAIL (modules missing)

- [ ] **Step 4: Implement `frontend/lib/merkle.ts`**

```ts
const enc = new TextEncoder();
export const LEAF_PREFIX = enc.encode("teluvane-anchor-leaf-v1:");
export const NODE_PREFIX = enc.encode("teluvane-anchor-node-v1:");

async function sha256(bytes: Uint8Array): Promise<Uint8Array> {
  const d = await crypto.subtle.digest("SHA-256", bytes);
  return new Uint8Array(d);
}

function concat(...parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(total);
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}

function fromHex(hex: string): Uint8Array {
  const h = hex.startsWith("0x") ? hex.slice(2) : hex;
  const out = new Uint8Array(h.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(h.substr(i * 2, 2), 16);
  return out;
}

function toHex(b: Uint8Array): string {
  return "0x" + Array.from(b).map((x) => x.toString(16).padStart(2, "0")).join("");
}

function cmp(a: Uint8Array, b: Uint8Array): number {
  for (let i = 0; i < a.length; i++) { if (a[i] !== b[i]) return a[i] - b[i]; }
  return 0;
}

export async function leafHash(orgId: string, sessionId: string, chainHeadHex: string): Promise<Uint8Array> {
  return sha256(concat(LEAF_PREFIX, enc.encode(orgId), enc.encode("|"),
    enc.encode(sessionId), enc.encode("|"), enc.encode(chainHeadHex)));
}

async function node(a: Uint8Array, b: Uint8Array): Promise<Uint8Array> {
  const [lo, ro] = cmp(a, b) <= 0 ? [a, b] : [b, a];
  return sha256(concat(NODE_PREFIX, lo, ro));
}

export async function rootFromProof(orgId: string, sessionId: string,
  chainHeadHex: string, proof: string[]): Promise<string> {
  let acc = await leafHash(orgId, sessionId, chainHeadHex);
  for (const sib of proof) acc = await node(acc, fromHex(sib));
  return toHex(acc);
}
```

- [ ] **Step 5: Implement `frontend/lib/chainVerify.ts`**

```ts
const enc = new TextEncoder();

async function sha256Hex(s: string): Promise<string> {
  const d = await crypto.subtle.digest("SHA-256", enc.encode(s));
  return Array.from(new Uint8Array(d)).map((x) => x.toString(16).padStart(2, "0")).join("");
}

export async function verifyChain(
  events: { seq: number; prev_hash: string; hash: string; canonical: string }[],
): Promise<{ ok: boolean; failAt?: number; head?: string }> {
  let prev = "GENESIS";
  for (const e of events) {
    if ((await sha256Hex(e.canonical)) !== e.hash) return { ok: false, failAt: e.seq };
    let parsedPrev: string;
    try { parsedPrev = JSON.parse(e.canonical).prev; } catch { return { ok: false, failAt: e.seq }; }
    if (parsedPrev !== prev) return { ok: false, failAt: e.seq };
    prev = e.hash;
  }
  return { ok: true, head: events.length ? events[events.length - 1].hash : undefined };
}
```

- [ ] **Step 6: Run, verify it passes**

Run: `cd frontend && npx vitest run lib/anchorVectors.test.ts`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/merkle.ts frontend/lib/chainVerify.ts frontend/lib/anchorVectors.test.ts frontend/lib/__fixtures__ frontend/scripts/sync-vectors.mjs frontend/package.json
git commit -m "feat: browser Merkle + chain verification, parity-tested against Python"
```

---

### Task 15: AnchorPanel component + dashboard integration

**Files:**
- Create: `frontend/components/AnchorPanel.tsx`
- Create: `frontend/components/AnchorPanel.test.tsx`
- Modify: `frontend/app/app/page.tsx` (render `<AnchorPanel>` in the session detail area; show the `anchor` dot in the session list)
- Modify: `frontend/package.json` (add `viem`)

**Interfaces:**
- Consumes: `apiFetch` from `@/lib/api`, `rootFromProof` from `@/lib/merkle`, `verifyChain` from `@/lib/chainVerify`, `viem` `createPublicClient`/`http`, `viem/chains` `avalancheFuji`
- Produces: `<AnchorPanel token={string} sessionId={string} />` default export

- [ ] **Step 1: Add viem**

`cd frontend && npm install viem`

- [ ] **Step 2: Write the failing test**

`frontend/components/AnchorPanel.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import AnchorPanel from "./AnchorPanel";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(async (path: string) => {
    if (path.endsWith("/canonical")) return [{ seq: 1, prev_hash: "GENESIS", hash: "h1",
      canonical: JSON.stringify({ prev: "GENESIS" }) }];
    if (path === "/anchor/contract") return { chain_id: 43113, contract_address: "0xC0",
      explorer_tx_url: "https://x/tx/", rpc_url: "http://rpc" };
    if (path.startsWith("/anchor/")) return { anchored: true, status: "verified",
      through_seq: 1, total_seq: 1, root: "0xroot", tx_hash: "0xtx", block_number: 9,
      head_stored: "h1", head_recomputed: "h1", head_matches: true, proof_ok: true };
    return {};
  }),
}));
vi.mock("@/lib/merkle", () => ({ rootFromProof: vi.fn(async () => "0xroot") }));
vi.mock("@/lib/chainVerify", () => ({ verifyChain: vi.fn(async () => ({ ok: true, head: "h1" })) }));
vi.mock("viem", () => ({
  createPublicClient: () => ({ readContract: vi.fn(async () => 1_700_000_000n) }),
  http: () => ({}),
}));
vi.mock("viem/chains", () => ({ avalancheFuji: { id: 43113 } }));

describe("AnchorPanel", () => {
  it("shows verified state when local + on-chain agree", async () => {
    render(<AnchorPanel token="t" sessionId="s1" />);
    await waitFor(() => expect(screen.getByText(/verified/i)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /0xtx/i })).toHaveAttribute(
      "href", "https://x/tx/0xtx");
  });

  it("shows mismatch when on-chain root is absent", async () => {
    const { rerender } = render(<AnchorPanel token="t" sessionId="s1" />);
    // override the mock to return 0n
    const viem = await import("viem");
    (viem.createPublicClient as any) = () => ({ readContract: async () => 0n });
    rerender(<AnchorPanel token="t" sessionId="s2" />);
    await waitFor(() => expect(screen.getByText(/does not match|mismatch/i)).toBeInTheDocument());
  });
});
```

- [ ] **Step 3: Run, verify it fails**

Run: `cd frontend && npx vitest run components/AnchorPanel.test.tsx`
Expected: FAIL (module missing)

- [ ] **Step 4: Implement `frontend/components/AnchorPanel.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { rootFromProof } from "@/lib/merkle";
import { verifyChain } from "@/lib/chainVerify";
import { createPublicClient, http } from "viem";
import { avalancheFuji } from "viem/chains";

type State =
  | { kind: "loading" }
  | { kind: "not-anchored" }
  | { kind: "pending" }
  | { kind: "verified"; onchainTs: number; tx: string; txUrl: string; block: number }
  | { kind: "mismatch"; why: string }
  | { kind: "rpc-unreachable" }
  | { kind: "proof-missing" };

const ABI = [{
  type: "function", name: "anchoredAt", stateMutability: "view",
  inputs: [{ name: "", type: "bytes32" }], outputs: [{ name: "", type: "uint256" }],
}] as const;

const DOT: Record<string, string> = {
  "not-anchored": "#8a8a8a", pending: "#c98a1b", verified: "#1f7a3d",
  mismatch: "#b4451f", "rpc-unreachable": "#8a8a8a", "proof-missing": "#b4451f",
};

export default function AnchorPanel({ token, sessionId }: { token: string; sessionId: string }) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [serverCheck, setServerCheck] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status: any = await apiFetch(`/anchor/${encodeURIComponent(sessionId)}`, { token });
        if (cancelled) return;
        setServerCheck(status.status);
        if (!status.anchored) { setState({ kind: "not-anchored" }); return; }
        if (!status.root || !Array.isArray(status_proof(status))) {
          setState({ kind: "proof-missing" }); return;
        }
        const contract: any = await apiFetch("/anchor/contract", { token });
        const events: any = await apiFetch(`/anchor/${encodeURIComponent(sessionId)}/canonical`, { token });
        const chain = await verifyChain(events);
        const localRoot = await rootFromProof(
          status.org_id ?? contract.org_id ?? "", sessionId, status.head_stored, status_proof(status));
        // org_id is not returned by /anchor; the public bundle carries it. For the
        // authed panel, the browser recomputes head from canonical events and
        // trusts the stored chain_head match instead. Use status.root directly:
        const client = createPublicClient({ chain: avalancheFuji, transport: http(contract.rpc_url || undefined) });
        let onchain: bigint;
        try {
          onchain = await client.readContract({
            address: contract.contract_address, abi: ABI, functionName: "anchoredAt",
            args: [status.root as `0x${string}`],
          }) as bigint;
        } catch {
          setState({ kind: "rpc-unreachable" }); return;
        }
        const headOk = chain.ok && chain.head === status.head_stored && status.head_matches;
        if (onchain > 0n && headOk) {
          setState({ kind: "verified", onchainTs: Number(onchain), tx: status.tx_hash,
            txUrl: (contract.explorer_tx_url || "") + status.tx_hash, block: status.block_number });
        } else if (status.status === "pending") {
          setState({ kind: "pending" });
        } else {
          setState({ kind: "mismatch",
            why: onchain === 0n ? "root not found on Avalanche" : "recomputed hash does not match" });
        }
      } catch {
        if (!cancelled) setState({ kind: "rpc-unreachable" });
      }
    })();
    return () => { cancelled = true; };
  }, [token, sessionId]);

  function status_proof(s: any): string[] { return s.proof ?? []; }

  const kind = state.kind === "loading" ? "not-anchored" : state.kind;
  return (
    <section aria-label="On-chain anchor" style={{ marginTop: "1.5rem" }}>
      <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 10, height: 10, borderRadius: "50%",
          background: DOT[kind] ?? "#8a8a8a", display: "inline-block" }} />
        Independent check, read from Avalanche
      </h3>
      {state.kind === "loading" && <p>Checking Avalanche...</p>}
      {state.kind === "not-anchored" && <p>This session is not anchored yet.</p>}
      {state.kind === "pending" && <p>Anchor transaction submitted, waiting for confirmations.</p>}
      {state.kind === "verified" && (
        <p>Verified. The Merkle root for this session was recorded on Avalanche Fuji at{" "}
          {new Date(state.onchainTs * 1000).toISOString()} in block {state.block}.{" "}
          <a href={state.txUrl}>{state.tx}</a></p>
      )}
      {state.kind === "mismatch" && <p style={{ color: DOT.mismatch }}>Does not match: {state.why}.</p>}
      {state.kind === "rpc-unreachable" && <p>Could not reach Avalanche RPC. Retry shortly.</p>}
      {state.kind === "proof-missing" && <p style={{ color: DOT["proof-missing"] }}>Anchor record incomplete.</p>}
      {serverCheck && <p style={{ fontSize: 13, color: "#666" }}>TELUVANE's check: {serverCheck}</p>}
    </section>
  );
}
```

Note: the `/anchor/{session_id}` response in Task 8 does NOT include `org_id` or
`proof`. Two options, pick one while implementing and keep the test in sync:
(a) add `org_id` and `proof` to the `verify_session` return dict (simplest,
harmless, both already known server-side), or (b) have the panel trust
`status.root` from the server and only independently verify chain + on-chain
presence (weaker). **Choose (a)**: extend `verify_session` in Task 8's file to
also return `"org_id": org_id` and `"proof": row["proof"]`, update
`tests/test_anchor_verify.py` to assert they are present, then the panel calls
`rootFromProof(status.org_id, sessionId, status.head_stored, status.proof)` and
compares to `status.root` before the on-chain read. Update this task's mock
accordingly.

- [ ] **Step 5: Wire into the dashboard**

In `frontend/app/app/page.tsx`: import `AnchorPanel`; where the selected
session's events/verdicts/chain status render, add
`{sessionId && <AnchorPanel token={token} sessionId={sessionId} />}`. In the
session list rows, add a dot before the session id colored by `row.anchor`
(`none` grey, `pending` amber, `mined` green, `failed`/`mismatch` red), text
label beside it. No pills.

- [ ] **Step 6: Run tests + build**

Run: `cd frontend && npx vitest run && npm run build`
Expected: PASS, build succeeds (set the `NEXT_PUBLIC_*` placeholders as CI does).

- [ ] **Step 7: Commit**

```bash
git add frontend/components/AnchorPanel.tsx frontend/components/AnchorPanel.test.tsx frontend/app/app/page.tsx frontend/package.json frontend/package-lock.json teluvane/anchor.py tests/test_anchor_verify.py
git commit -m "feat: AnchorPanel trustless verification in the dashboard"
```

---

### Task 16: Public `/verify` page

**Files:**
- Create: `frontend/app/verify/page.tsx`
- Create: `frontend/app/verify/VerifyClient.tsx`
- Create: `frontend/app/verify/VerifyClient.test.tsx`
- Modify: `frontend/app/sitemap.ts` (add `/verify`)

**Interfaces:**
- Consumes: `fetch` to `${NEXT_PUBLIC_API_URL}/verify/public/{id}`, `rootFromProof`, `verifyChain`, viem
- Produces: a no-login page with two inputs (session id, or pasted evidence-pack JSON) that runs the same verification as `AnchorPanel` and renders the six states.

- [ ] **Step 1: Write the failing test**

`frontend/app/verify/VerifyClient.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import VerifyClient from "./VerifyClient";

vi.mock("@/lib/merkle", () => ({ rootFromProof: vi.fn(async () => "0xroot") }));
vi.mock("@/lib/chainVerify", () => ({ verifyChain: vi.fn(async () => ({ ok: true, head: "h1" })) }));
vi.mock("viem", () => ({ createPublicClient: () => ({ readContract: async () => 1700000000n }), http: () => ({}) }));
vi.mock("viem/chains", () => ({ avalancheFuji: { id: 43113 } }));

globalThis.fetch = vi.fn(async () => ({
  ok: true,
  json: async () => ({
    session_id: "s1", canonical: [{ seq: 1, prev_hash: "GENESIS", hash: "h1",
      canonical: JSON.stringify({ prev: "GENESIS" }) }],
    proof: [], chain_head: "h1", root: "0xroot", tx_hash: "0xtx",
    chain_id: 43113, contract_address: "0xC0", explorer_tx_url: "https://x/tx/", rpc_url: "http://rpc",
    verify: { org_id: "org1" },
  }),
})) as any;

describe("VerifyClient", () => {
  it("verifies a public session id", async () => {
    render(<VerifyClient />);
    fireEvent.change(screen.getByLabelText(/session id/i), { target: { value: "s1" } });
    fireEvent.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() => expect(screen.getByText(/verified/i)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd frontend && npx vitest run app/verify/VerifyClient.test.tsx`
Expected: FAIL

- [ ] **Step 3: Implement**

`frontend/app/verify/page.tsx` (server component shell):

```tsx
import type { Metadata } from "next";
import VerifyClient from "./VerifyClient";

export const metadata: Metadata = {
  title: "Verify a TELUVANE session on Avalanche",
  description: "Check that an AI agent session log is unaltered, using Avalanche, with no account.",
};

export default function VerifyPage() {
  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "3rem 1.25rem", lineHeight: 1.55 }}>
      <h1>Verify a session</h1>
      <p>Confirm that a TELUVANE agent session log has not changed since it was
        recorded. Verification runs in your browser and reads Avalanche Fuji
        directly. TELUVANE cannot influence the result.</p>
      <VerifyClient />
    </main>
  );
}
```

`frontend/app/verify/VerifyClient.tsx`: a `"use client"` component with:
- A text input `aria-label="session id"` + Verify button that calls
  `fetch(`${process.env.NEXT_PUBLIC_API_URL}/verify/public/${id}`)`.
- A `<textarea aria-label="evidence pack JSON">` + Verify button that parses the
  pasted JSON (expects `{ anchor: {...}, events: [...] }` shape from the evidence
  pack's `json` output plus the `canonical`/`proof` fields; if the pack lacks
  `canonical`, tell the user to use a pack exported after this feature shipped).
- Shared `runVerification(bundle)` that does: `verifyChain(bundle.canonical)` ->
  `rootFromProof(bundle.verify.org_id, bundle.session_id, bundle.chain_head, bundle.proof)`
  -> compare to `bundle.root` -> `createPublicClient` read `anchoredAt(root)` ->
  render one of the six states (reuse the exact state machine + `DOT` colors from
  `AnchorPanel`; extract that into `frontend/lib/anchorState.ts` shared by both
  and unit-test it once).
- On `fetch` non-200: show "No public record for this session id."

- [ ] **Step 4: Refactor shared state logic**

Extract the state machine + `DOT` map into `frontend/lib/anchorState.ts` with a
pure function `decideState(input): State` and a test
`frontend/lib/anchorState.test.ts` covering all six branches. Update
`AnchorPanel.tsx` to import it.

- [ ] **Step 5: Run, verify it passes**

Run: `cd frontend && npx vitest run && npm run build`
Expected: PASS + build OK

- [ ] **Step 6: Commit**

```bash
git add frontend/app/verify frontend/lib/anchorState.ts frontend/lib/anchorState.test.ts frontend/components/AnchorPanel.tsx frontend/app/sitemap.ts
git commit -m "feat: public /verify page"
```

---

### Task 17: Docs, env samples, README, final integration pass

**Files:**
- Modify: `README.md` (canonical URL to `teluvane.com`; add an "On-chain anchoring" subsection under How it works)
- Modify: `docs/` any architecture doc that has the mermaid diagram (add the anchor + Avalanche node)
- Create: `docs/onchain-anchoring.md` (operator + auditor reference)
- Modify: `.env.example` / deployment env docs with all `ANCHOR_*` vars

- [ ] **Step 1: README**

- Replace `blackbox-agent-accountability.vercel.app` with `teluvane.com` in the badge and links.
- Add under "How it works" a row/paragraph: sessions are Merkle-batched and their
  root anchored to `SessionAnchorRegistry` on Avalanche Fuji; anyone can verify
  at `teluvane.com/verify`. One paragraph, plain language, no hype words.

- [ ] **Step 2: `docs/onchain-anchoring.md`**

Cover: what is written on chain (root + count, never content), the point-in-time
model (`anchored_through_seq`), the tamper-detection matrix from spec §10, how to
verify manually (recompute head from canonical events, recompute root from proof,
read `anchoredAt` on Snowtrace), the env vars, and the milestone roadmap.

- [ ] **Step 3: Full test sweep**

Run: `pytest -q && cd frontend && npx vitest run && npm run build && cd ../contracts && forge test`
Expected: all green.

- [ ] **Step 4: Update the memory file**

Append to `/home/weslax83/.claude/projects/-home-weslax83-teluvane/memory/teluvane-avalanche-anchoring.md`: implementation done, branch, key module names (`teluvane/anchor.py`, `anchor_chain.py`, `anchor_store.py`, `merkle.py`, `contracts/SessionAnchorRegistry.sol`, `frontend/components/AnchorPanel.tsx`, `frontend/app/verify`).

- [ ] **Step 5: Commit**

```bash
git add README.md docs/ .env.example
git commit -m "docs: on-chain anchoring reference and README update"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Task |
|---|---|
| §1 contract | 12 |
| §2 Merkle | 2 (Python), 14 (TS) |
| §3 data model | 1 |
| §4 anchor module (config, pending, run, reconcile, verify, health) | 4, 5, 6, 7, 8 |
| §5 scheduler | 9 |
| §6 API routes + `/sessions` field | 10 |
| §7 config env | 4 (backend), 13 (samples) |
| §8 dashboard panel + public page + opt-in | 15, 16, 10 (opt-in route) |
| §9 evidence pack | 11 |
| §10 tamper matrix | 8 (behavior), 17 (doc) |
| §11 testing | every task is TDD; contract 12; parity 14 |
| §12 observability (`/anchor/status`, batch logs) | 8, 10 |
| §13 milestone split | 17 (doc) |
| digest strategy option B | 3, 10 (`/canonical` route), 14 |
| `_event_digest` frozen | 3 (refactor keeps bytes identical; `test_store.py` regression gate) |

No gaps.

**2. Placeholder scan:** The `_auth` / seeding helpers in Tasks 10, 15, 16 tests
are marked `...` deliberately with an instruction to copy the concrete pattern
from a named existing test file (`tests/test_api.py`, `tests/test_anchor_verify.py`).
Every implementation step has real code. The `verify_session` scaffolding note in
Task 8 explicitly says to delete the dead lines and use the `merkle.root_from_proof`
helper. Acceptable, but the executor MUST read the referenced test files.

**3. Type consistency:**
- `merkle.build_tree` returns `(root_str, {(org,session): proof})` in Tasks 2, 6, 8 — consistent.
- `verify_session` return dict keys are defined in Task 8 interface and consumed in Tasks 10, 11, 15 — Task 15 requires adding `org_id` and `proof` to that dict; Task 15 Step 4 calls this out and updates Task 8's test. Fixed inline here: **Task 8 implementation must include `"org_id": org_id` and `"proof": row["proof"]` in the returned dict**, and `tests/test_anchor_verify.py` should assert their presence.
- `anchor_store.latest_anchor` row shape (has `status`, `tx_hash`, `chain_head`, `proof`, `anchored_through_seq`, `block_number`, `confirmations`, `mined_at`) — consistent across Tasks 1, 8, 10.
- `AnchorConfig` field names identical in Tasks 4, 5, 6, 7, 8, 10.
- Frontend: `rootFromProof(orgId, sessionId, chainHeadHex, proof)` signature identical in Tasks 14, 15, 16.

Fix applied inline: Task 8 interface list updated to include `org_id` and `proof` in the `verify_session` return.
