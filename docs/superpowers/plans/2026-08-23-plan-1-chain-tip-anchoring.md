# Plan 1 — Chain-tip Anchoring to Avalanche C-Chain

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give TELUVANE's existing hash-chain tamper-evidence claim an independent, publicly
verifiable witness by periodically batch-anchoring session tip hashes to Avalanche C-Chain, and
expose a public (no-auth) endpoint so anyone can check a session's chain against the on-chain
record without trusting TELUVANE's database.

**Architecture:** A pure, network-free Merkle-tree module (`teluvane/anchor.py`) builds a batch
root from every Pro-plan org's active session tip hashes; a thin web3.py client (injectable
provider, no real network calls in tests) signs and sends one `anchor(bytes32)` transaction per
batch to a minimal `TeluvaneAnchorRegistry.sol` contract; a new `chain_anchors` table stores one
row per `(session, batch)` with that session's Merkle proof; a new scheduler tick (same
in-process-APScheduler shape as `teluvane/scheduler.py`'s existing tribunal scheduler) drives it
periodically for Pro orgs; a new public endpoint recomputes and cross-checks everything without
requiring an account.

**Spec:** `docs/superpowers/specs/2026-08-23-blockchain-trust-layer-design.md`

**Tech stack:** Python 3.11, `web3.py` (new dependency), Solidity ^0.8.24 (new, minimal, no
framework needed for v1 — deploy via a plain script using web3.py's own contract-deploy
helpers, no Hardhat/Foundry toolchain required for one tiny contract), Avalanche Fuji testnet
for development/CI-adjacent manual verification, Postgres (existing), pytest (existing).

**Prerequisite:** A Fuji testnet wallet funded with test AVAX (from the Avalanche faucet) for
manual Step verification in Tasks 3–5. CI never touches a real network (see Task 3).

---

### Task 1: Pure Merkle-tree helpers (no blockchain dependency)

**Files:**
- Create: `teluvane/merkle.py`
- Test: `tests/test_merkle.py`

**Interfaces:**
- Produces: `build_merkle_tree(leaves: list[bytes]) -> MerkleTree`, `MerkleTree.root: bytes`,
  `MerkleTree.proof(index: int) -> list[tuple[bytes, bool]]` (sibling hash + "is-left" flag per
  level), `verify_merkle_proof(leaf: bytes, proof: list[tuple[bytes, bool]], root: bytes) ->
  bool`. Used by Task 4 (batcher) and the public verify endpoint (Task 7) — the latter must be
  able to verify a proof with zero dependency on the tree-building code, so a caller can't be
  fooled by a bug shared between "prove" and "verify."

- [ ] **Step 1: Write the failing test**

Create `tests/test_merkle.py`:
```python
import hashlib
from teluvane.merkle import build_merkle_tree, verify_merkle_proof

def _h(s: str) -> bytes:
    return hashlib.sha256(s.encode()).digest()

def test_single_leaf_root_is_the_leaf_itself():
    tree = build_merkle_tree([_h("only-one")])
    assert tree.root == _h("only-one")

def test_proof_verifies_for_every_leaf_in_a_four_leaf_tree():
    leaves = [_h(f"leaf-{i}") for i in range(4)]
    tree = build_merkle_tree(leaves)
    for i, leaf in enumerate(leaves):
        proof = tree.proof(i)
        assert verify_merkle_proof(leaf, proof, tree.root)

def test_proof_fails_for_a_tampered_leaf():
    leaves = [_h(f"leaf-{i}") for i in range(4)]
    tree = build_merkle_tree(leaves)
    proof = tree.proof(0)
    assert not verify_merkle_proof(_h("tampered"), proof, tree.root)

def test_odd_leaf_count_duplicates_the_last_leaf_to_pair(): 
    # Standard Merkle convention: an unpaired last leaf is paired with itself so the tree
    # stays binary. Three leaves must still produce valid, distinct proofs for all three.
    leaves = [_h(f"leaf-{i}") for i in range(3)]
    tree = build_merkle_tree(leaves)
    for i, leaf in enumerate(leaves):
        assert verify_merkle_proof(leaf, tree.proof(i), tree.root)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_merkle.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'teluvane.merkle'`

- [ ] **Step 3: Write minimal implementation**

Create `teluvane/merkle.py`:
```python
# teluvane/teluvane/merkle.py
import hashlib
from dataclasses import dataclass

def _pair_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(left + right).digest()

@dataclass
class MerkleTree:
    levels: list[list[bytes]]   # levels[0] = leaves, levels[-1] = [root]

    @property
    def root(self) -> bytes:
        return self.levels[-1][0]

    def proof(self, index: int) -> list[tuple[bytes, bool]]:
        """Sibling hash + is_left (True if the sibling belongs on the left when re-hashing)
        for each level from the leaf up to (but not including) the root."""
        path: list[tuple[bytes, bool]] = []
        i = index
        for level in self.levels[:-1]:
            is_right = i % 2 == 1
            sibling_i = i - 1 if is_right else i + 1
            sibling_i = min(sibling_i, len(level) - 1)
            path.append((level[sibling_i], not is_right))
            i //= 2
        return path

def build_merkle_tree(leaves: list[bytes]) -> MerkleTree:
    if not leaves:
        raise ValueError("cannot build a Merkle tree from zero leaves")
    levels = [list(leaves)]
    while len(levels[-1]) > 1:
        cur = levels[-1]
        if len(cur) % 2 == 1:
            cur = cur + [cur[-1]]   # duplicate the last leaf to keep the tree binary
        nxt = [_pair_hash(cur[i], cur[i + 1]) for i in range(0, len(cur), 2)]
        levels.append(nxt)
    return MerkleTree(levels=levels)

def verify_merkle_proof(leaf: bytes, proof: list[tuple[bytes, bool]], root: bytes) -> bool:
    cur = leaf
    for sibling, sibling_is_left in proof:
        cur = _pair_hash(sibling, cur) if sibling_is_left else _pair_hash(cur, sibling)
    return cur == root
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_merkle.py -v`
Expected: PASS, all 4 tests.

- [ ] **Step 5: Commit**

```bash
git add teluvane/merkle.py tests/test_merkle.py
git commit -m "feat: add pure Merkle-tree helpers for batch anchoring"
```

---

### Task 2: `chain_anchors` migration + Store read/write methods

**Files:**
- Create: `migrations/0012_chain_anchors.sql`
- Modify: `teluvane/store.py`
- Test: `tests/test_store.py` (add cases)

**Interfaces:**
- Produces: `Store.add_anchor(org_id, session_id, batch_id, tip_seq, tip_hash, merkle_proof,
  merkle_root, tx_hash, block_number, chain_id) -> None`, `Store.latest_anchor(org_id,
  session_id) -> dict | None`, `Store.session_tip(org_id, session_id) -> tuple[int, str] | None`
  (returns `(seq, hash)` of the latest event, or `None` for an empty/nonexistent session).
- Consumes: the existing `_assert_scoped` guard — every new method follows the same
  `org_id`-first, scoped-query pattern as every other `Store` method.

- [ ] **Step 1: Write the migration**

Create `migrations/0012_chain_anchors.sql`:
```sql
-- 0012: on-chain anchor records for the hash chain (Avalanche C-Chain batch anchoring)
CREATE TABLE IF NOT EXISTS chain_anchors (
    id            BIGSERIAL PRIMARY KEY,
    batch_id      TEXT NOT NULL,
    org_id        TEXT NOT NULL,
    session_id    TEXT NOT NULL,
    tip_seq       BIGINT NOT NULL,
    tip_hash      TEXT NOT NULL,
    merkle_proof  JSONB NOT NULL,
    merkle_root   TEXT NOT NULL,
    tx_hash       TEXT NOT NULL,
    block_number  BIGINT,
    chain_id      INTEGER NOT NULL DEFAULT 43114,
    anchored_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chain_anchors_org_session_tip
    ON chain_anchors (org_id, session_id, tip_seq DESC);
```

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_store.py` (follow the existing file's fixture/setup pattern — it already has
a `store` fixture wired to `TEST_DATABASE_URL` with migrations applied; read the top of the file
first to match it exactly):
```python
def test_add_and_read_latest_anchor(store):
    org_id = "org-anchor-test"
    store.append(org_id, Event(agent_id="a1", session_id="s1", kind="tool_call"))
    seq, tip_hash = store.session_tip(org_id, "s1")
    store.add_anchor(org_id, "s1", batch_id="batch-1", tip_seq=seq, tip_hash=tip_hash,
                     merkle_proof=[["deadbeef", True]], merkle_root="feedface",
                     tx_hash="0xabc123", block_number=42, chain_id=43114)
    anchor = store.latest_anchor(org_id, "s1")
    assert anchor["tip_hash"] == tip_hash
    assert anchor["tx_hash"] == "0xabc123"
    assert anchor["merkle_root"] == "feedface"

def test_latest_anchor_returns_the_most_recent_by_tip_seq(store):
    org_id = "org-anchor-test-2"
    store.append(org_id, Event(agent_id="a1", session_id="s1", kind="tool_call"))
    seq1, hash1 = store.session_tip(org_id, "s1")
    store.add_anchor(org_id, "s1", batch_id="b1", tip_seq=seq1, tip_hash=hash1,
                     merkle_proof=[], merkle_root="r1", tx_hash="0x1", block_number=1, chain_id=43114)
    store.append(org_id, Event(agent_id="a1", session_id="s1", kind="tool_result"))
    seq2, hash2 = store.session_tip(org_id, "s1")
    store.add_anchor(org_id, "s1", batch_id="b2", tip_seq=seq2, tip_hash=hash2,
                     merkle_proof=[], merkle_root="r2", tx_hash="0x2", block_number=2, chain_id=43114)
    assert store.latest_anchor(org_id, "s1")["tx_hash"] == "0x2"

def test_latest_anchor_is_none_for_an_unanchored_session(store):
    org_id = "org-anchor-test-3"
    store.append(org_id, Event(agent_id="a1", session_id="s1", kind="tool_call"))
    assert store.latest_anchor(org_id, "s1") is None

def test_session_tip_is_none_for_an_empty_session(store):
    assert store.session_tip("org-anchor-test-4", "no-such-session") is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `DATABASE_URL="${TEST_DATABASE_URL:-postgresql://localhost:5432/teluvane_test}" pytest tests/test_store.py -k anchor -v`
Expected: FAIL — `AttributeError: 'Store' object has no attribute 'add_anchor'` (and similarly
for `latest_anchor`/`session_tip`).

- [ ] **Step 4: Add the methods to `teluvane/store.py`**

```python
    def session_tip(self, org_id: str, session_id: str) -> Optional[tuple[int, str]]:
        sql = "SELECT seq, hash FROM events WHERE org_id=%s AND session_id=%s ORDER BY seq DESC LIMIT 1"
        self._assert_scoped(org_id, sql)
        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (org_id, session_id))
            row = cur.fetchone()
        return (row["seq"], row["hash"]) if row else None

    def add_anchor(self, org_id: str, session_id: str, *, batch_id: str, tip_seq: int,
                   tip_hash: str, merkle_proof: list, merkle_root: str, tx_hash: str,
                   block_number: Optional[int], chain_id: int = 43114) -> None:
        sql = ("INSERT INTO chain_anchors"
               "(org_id,session_id,batch_id,tip_seq,tip_hash,merkle_proof,merkle_root,"
               "tx_hash,block_number,chain_id)"
               " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)")
        self._assert_scoped(org_id, sql)
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (org_id, session_id, batch_id, tip_seq, tip_hash,
                                  json.dumps(merkle_proof), merkle_root, tx_hash,
                                  block_number, chain_id))
            conn.commit()

    def latest_anchor(self, org_id: str, session_id: str) -> Optional[dict]:
        sql = ("SELECT * FROM chain_anchors WHERE org_id=%s AND session_id=%s "
               "ORDER BY tip_seq DESC LIMIT 1")
        self._assert_scoped(org_id, sql)
        with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (org_id, session_id))
            row = cur.fetchone()
        return dict(row) if row else None
```

Add these as new methods on the `Store` class in `teluvane/store.py`, placed after
`verify_chain` (keep the file's existing "writes" / "reads" comment-banner grouping — these are
one write, two reads).

- [ ] **Step 5: Run tests to verify they pass**

Run: `DATABASE_URL="${TEST_DATABASE_URL:-postgresql://localhost:5432/teluvane_test}" pytest tests/test_store.py -k anchor -v`
Expected: PASS, all 4 new tests.

- [ ] **Step 6: Run the full store suite to check nothing else broke**

Run: `DATABASE_URL="${TEST_DATABASE_URL:-postgresql://localhost:5432/teluvane_test}" pytest tests/test_store.py tests/test_migrate.py -v`
Expected: all PASS (existing 19 store tests + migration test still green).

- [ ] **Step 7: Commit**

```bash
git add migrations/0012_chain_anchors.sql teluvane/store.py tests/test_store.py
git commit -m "feat: add chain_anchors table and Store anchor read/write methods"
```

---

### Task 3: `AnchorClient` — injectable web3.py wrapper

**Files:**
- Modify: `pyproject.toml` (dependencies)
- Modify: `requirements.txt`
- Create: `teluvane/anchor.py`
- Test: `tests/test_anchor.py`

**Interfaces:**
- Produces: `AnchorClient(w3, contract_address, private_key)` with `.anchor(root: bytes) ->
  AnchorReceipt` (`tx_hash`, `block_number`). `w3` is an injected `web3.Web3` instance —
  production code builds it against a real Avalanche RPC URL; tests inject `web3.py`'s own
  `EthereumTesterProvider` (in-memory, no network), matching how `run_lens` in `tribunal.py`
  already accepts an injectable `llm` for the same reason (§11 of the spec).

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add to `dependencies`:
```toml
    "web3>=6.15,<7.0",
```
In `requirements.txt`, add:
```
web3>=6.15,<7.0
```
Then: `pip install -e ".[dev]"`

- [ ] **Step 2: Write the failing test**

Create `tests/test_anchor.py`:
```python
import hashlib
import pytest
from web3 import Web3, EthereumTesterProvider
from teluvane.anchor import AnchorClient, deploy_registry_for_test

@pytest.fixture
def w3():
    return Web3(EthereumTesterProvider())

def test_anchor_sends_a_transaction_and_returns_a_receipt(w3):
    account = w3.eth.accounts[0]
    contract_address = deploy_registry_for_test(w3, deployer=account)
    client = AnchorClient(w3, contract_address=contract_address, account=account)
    root = hashlib.sha256(b"test-root").digest()
    receipt = client.anchor(root)
    assert receipt.tx_hash
    assert receipt.block_number is not None

def test_anchor_emits_the_root_in_an_event(w3):
    account = w3.eth.accounts[0]
    contract_address = deploy_registry_for_test(w3, deployer=account)
    client = AnchorClient(w3, contract_address=contract_address, account=account)
    root = hashlib.sha256(b"another-root").digest()
    receipt = client.anchor(root)
    logs = client.get_anchored_logs(from_block=receipt.block_number, to_block=receipt.block_number)
    assert any(log["root"] == root for log in logs)
```

`deploy_registry_for_test` is a small test-only helper (also lives in `teluvane/anchor.py`,
guarded by nothing special — it's just a plain function, only ever called from tests) that
compiles and deploys `TeluvaneAnchorRegistry.sol` against the injected tester provider, so the
test suite never depends on a pre-deployed contract address. (Compilation approach: Step 4 below
uses `py-solc-x` at test-fixture time rather than requiring a separate Node/Foundry toolchain in
CI — install `solcx` as a `dev` extra alongside `pytest`/`respx`.)

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_anchor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'teluvane.anchor'`

- [ ] **Step 4: Add `py-solc-x` as a dev dependency**

In `pyproject.toml`'s `[project.optional-dependencies]` `dev` array, add `"py-solc-x>=2.0"`.
Then: `pip install -e ".[dev]"` and, once per machine, `python -c "import solcx;
solcx.install_solc('0.8.24')"` to fetch the compiler binary (cached locally after first run; CI
should cache `~/.solcx` the same way it already caches `pip`'s cache directory, per
`.github/workflows/ci.yml` — read that file first to match its existing cache-step style).

- [ ] **Step 5: Write the contract source + minimal implementation**

Create `contracts/TeluvaneAnchorRegistry.sol` (matches the spec's §8 exactly):
```solidity
// SPDX-License-Identifier: AGPL-3.0-or-later
pragma solidity ^0.8.24;

contract TeluvaneAnchorRegistry {
    address public immutable owner;
    event Anchored(bytes32 indexed root, uint256 timestamp);

    constructor() { owner = msg.sender; }

    function anchor(bytes32 root) external {
        require(msg.sender == owner, "not authorized");
        emit Anchored(root, block.timestamp);
    }
}
```

Create `teluvane/anchor.py`:
```python
# teluvane/teluvane/anchor.py
from dataclasses import dataclass
from pathlib import Path
import solcx

_CONTRACT_PATH = Path(__file__).resolve().parent.parent / "contracts" / "TeluvaneAnchorRegistry.sol"

def _compiled():
    solcx.install_solc("0.8.24", show_progress=False)
    out = solcx.compile_files([str(_CONTRACT_PATH)], output_values=["abi", "bin"], solc_version="0.8.24")
    key = f"{_CONTRACT_PATH}:TeluvaneAnchorRegistry"
    return out[key]["abi"], out[key]["bin"]

def deploy_registry_for_test(w3, deployer: str) -> str:
    """Test-only helper: compiles and deploys the registry against an injected (in-memory or
    testnet) web3 provider. Never used against Avalanche C-Chain mainnet directly — the real
    mainnet address is deployed once, out of band, and configured via env var."""
    abi, bytecode = _compiled()
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = Contract.constructor().transact({"from": deployer})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt.contractAddress

@dataclass
class AnchorReceipt:
    tx_hash: str
    block_number: int | None

class AnchorClient:
    """Signs and sends `anchor(bytes32)` transactions. `w3` is injected so tests use an
    in-memory provider and production code uses a real Avalanche C-Chain RPC endpoint --
    the class itself never knows which."""
    _ABI = [
        {"inputs": [{"internalType": "bytes32", "name": "root", "type": "bytes32"}],
         "name": "anchor", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
        {"anonymous": False, "inputs": [
            {"indexed": True, "internalType": "bytes32", "name": "root", "type": "bytes32"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}],
         "name": "Anchored", "type": "event"},
    ]

    def __init__(self, w3, contract_address: str, account: str):
        self.w3 = w3
        self.account = account
        self.contract = w3.eth.contract(address=contract_address, abi=self._ABI)

    def anchor(self, root: bytes) -> AnchorReceipt:
        tx_hash = self.contract.functions.anchor(root).transact({"from": self.account})
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return AnchorReceipt(tx_hash=receipt.transactionHash.hex(), block_number=receipt.blockNumber)

    def get_anchored_logs(self, from_block: int, to_block: int) -> list[dict]:
        events = self.contract.events.Anchored().get_logs(from_block=from_block, to_block=to_block)
        return [{"root": e["args"]["root"], "timestamp": e["args"]["timestamp"]} for e in events]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_anchor.py -v`
Expected: PASS, both tests. (First run downloads/compiles the solc binary — slower; subsequent
runs use the cached compiler and cached bytecode-compile output.)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml requirements.txt contracts/TeluvaneAnchorRegistry.sol teluvane/anchor.py tests/test_anchor.py
git commit -m "feat: add TeluvaneAnchorRegistry contract and injectable AnchorClient"
```

---

### Task 4: Batcher — collect due sessions, build tree, anchor, persist

**Files:**
- Modify: `teluvane/anchor.py`
- Test: `tests/test_anchor.py` (add cases)

**Interfaces:**
- Produces: `run_anchor_batch(store, client: AnchorClient, org_ids: list[str]) -> dict` (returns
  `{sessions_anchored: int, tx_hash: str | None}`; `None` tx_hash means nothing was due).
- Consumes: `Store.session_tip`, `Store.add_anchor` (Task 2), `build_merkle_tree`/`.proof` (Task
  1), `AnchorClient.anchor` (Task 3).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_anchor.py`:
```python
from teluvane.anchor import run_anchor_batch
from teluvane.schema import Event

def test_run_anchor_batch_anchors_every_session_with_new_events(w3, store):
    account = w3.eth.accounts[0]
    contract_address = deploy_registry_for_test(w3, deployer=account)
    client = AnchorClient(w3, contract_address=contract_address, account=account)
    org_id = "org-batch-test"
    store.append(org_id, Event(agent_id="a1", session_id="s1", kind="tool_call"))
    store.append(org_id, Event(agent_id="a1", session_id="s2", kind="tool_call"))

    result = run_anchor_batch(store, client, org_ids=[org_id])

    assert result["sessions_anchored"] == 2
    assert result["tx_hash"]
    for session_id in ("s1", "s2"):
        anchor = store.latest_anchor(org_id, session_id)
        assert anchor is not None
        assert anchor["tx_hash"] == result["tx_hash"]

def test_run_anchor_batch_is_a_noop_when_nothing_is_due(w3, store):
    account = w3.eth.accounts[0]
    contract_address = deploy_registry_for_test(w3, deployer=account)
    client = AnchorClient(w3, contract_address=contract_address, account=account)
    result = run_anchor_batch(store, client, org_ids=["org-with-no-sessions"])
    assert result == {"sessions_anchored": 0, "tx_hash": None}

def test_a_session_already_anchored_at_its_current_tip_is_skipped(w3, store):
    account = w3.eth.accounts[0]
    contract_address = deploy_registry_for_test(w3, deployer=account)
    client = AnchorClient(w3, contract_address=contract_address, account=account)
    org_id = "org-batch-test-2"
    store.append(org_id, Event(agent_id="a1", session_id="s1", kind="tool_call"))
    run_anchor_batch(store, client, org_ids=[org_id])          # anchors once
    result = run_anchor_batch(store, client, org_ids=[org_id])  # no new events since
    assert result == {"sessions_anchored": 0, "tx_hash": None}
```

(This test file's `store` fixture is presumed already defined per `tests/test_store.py`'s
existing fixture — if `tests/test_anchor.py` doesn't share `conftest.py` fixtures automatically,
check `tests/conftest.py` first and reuse whatever fixture name the rest of the suite already
uses, per this repo's existing convention, rather than defining a second one.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_anchor.py -k run_anchor_batch -v`
Expected: FAIL — `ImportError: cannot import name 'run_anchor_batch'`

- [ ] **Step 3: Write minimal implementation**

Add to `teluvane/anchor.py`:
```python
import uuid
from .merkle import build_merkle_tree

def run_anchor_batch(store, client: "AnchorClient", org_ids: list[str]) -> dict:
    leaves: list[bytes] = []
    pending: list[tuple[str, str, int, str]] = []   # (org_id, session_id, tip_seq, tip_hash)
    for org_id in org_ids:
        for session in store.sessions(org_id):
            session_id = session["session_id"]
            tip = store.session_tip(org_id, session_id)
            if tip is None:
                continue
            tip_seq, tip_hash = tip
            existing = store.latest_anchor(org_id, session_id)
            if existing is not None and existing["tip_seq"] == tip_seq:
                continue   # already anchored at this exact tip; nothing new to prove
            leaves.append(bytes.fromhex(tip_hash) if _looks_like_hex(tip_hash)
                          else tip_hash.encode("utf-8"))
            pending.append((org_id, session_id, tip_seq, tip_hash))

    if not pending:
        return {"sessions_anchored": 0, "tx_hash": None}

    tree = build_merkle_tree(leaves)
    receipt = client.anchor(tree.root)
    batch_id = str(uuid.uuid4())
    for i, (org_id, session_id, tip_seq, tip_hash) in enumerate(pending):
        proof = [[sib.hex(), is_left] for sib, is_left in tree.proof(i)]
        store.add_anchor(org_id, session_id, batch_id=batch_id, tip_seq=tip_seq,
                         tip_hash=tip_hash, merkle_proof=proof, merkle_root=tree.root.hex(),
                         tx_hash=receipt.tx_hash, block_number=receipt.block_number)
    return {"sessions_anchored": len(pending), "tx_hash": receipt.tx_hash}

def _looks_like_hex(s: str) -> bool:
    try:
        bytes.fromhex(s)
        return len(s) % 2 == 0
    except ValueError:
        return False
```

Note the digest hashes stored by `_event_digest` in `store.py` are hex-encoded SHA-256 strings
(64 hex chars); `_looks_like_hex` exists because `"GENESIS"` (the sentinel `prev_hash` for an
empty chain, per `store.py`) is not valid hex and must fall back to a plain UTF-8 encode instead
of crashing — read `store.py`'s `_event_digest` again here to confirm a session's *tip* hash
(as opposed to `prev_hash`) is always a real SHA-256 hex digest in practice (it is, since `hash`
is always the output of `_event_digest`, never the `"GENESIS"` sentinel itself) before deciding
whether this fallback branch is even reachable for tip hashes specifically — if it's provably
unreachable, simplify to a plain `bytes.fromhex(tip_hash)` and drop the helper.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_anchor.py -v`
Expected: PASS, all 5 tests (2 from Task 3 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add teluvane/anchor.py tests/test_anchor.py
git commit -m "feat: add batch anchoring across sessions with skip-if-unchanged"
```

---

### Task 5: Scheduler integration (Pro-plan orgs, periodic tick)

**Files:**
- Modify: `teluvane/scheduler.py`
- Test: `tests/test_scheduler.py` (add cases)

**Interfaces:**
- Produces: `run_due_anchors(store, client) -> dict[str, int]` — same shape as the existing
  `run_due_schedules` (org_id -> count), listing every org on the Pro plan (anchoring, unlike
  tribunal scheduling, isn't itself opt-in/configurable per org for v1 — every Pro org gets
  anchored on a fixed interval; a per-org toggle can be added later if anyone asks to opt out).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_scheduler.py` (match the existing file's mocking style for `org_plan` — read
it first):
```python
def test_run_due_anchors_only_includes_pro_orgs(monkeypatch, store, fake_anchor_client):
    from teluvane import scheduler
    monkeypatch.setattr(scheduler, "org_plan", lambda org_id: "pro" if org_id == "pro-org" else "free")
    store.append("pro-org", Event(agent_id="a1", session_id="s1", kind="tool_call"))
    store.append("free-org", Event(agent_id="a1", session_id="s1", kind="tool_call"))
    result = scheduler.run_due_anchors(store, fake_anchor_client, all_org_ids=["pro-org", "free-org"])
    assert result == {"pro-org": 1}
```

(`fake_anchor_client` is a small test fixture — a stand-in `AnchorClient`-shaped object backed
by the Task 3/4 in-memory `w3`/`EthereumTesterProvider` setup; define it in `tests/conftest.py`
if other test files will want it too, following whatever pattern `tests/conftest.py` already
uses for shared fixtures like `store` — read that file first.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scheduler.py -k anchors -v`
Expected: FAIL — `AttributeError: module 'teluvane.scheduler' has no attribute 'run_due_anchors'`

- [ ] **Step 3: Write minimal implementation**

Add to `teluvane/scheduler.py`:
```python
from .anchor import run_anchor_batch

def run_due_anchors(store, client, all_org_ids: list[str]) -> dict[str, int]:
    """Anchor every Pro-plan org's due sessions. Unlike tribunal scheduling this has no
    per-org enable/interval row yet -- v1 anchors every Pro org on each tick this is called
    from, relying on run_anchor_batch's own skip-if-unchanged check to make repeated ticks
    cheap for orgs with no new activity."""
    ran: dict[str, int] = {}
    for org_id in all_org_ids:
        if org_plan(org_id) != "pro":
            continue
        result = run_anchor_batch(store, client, org_ids=[org_id])
        if result["sessions_anchored"] > 0:
            ran[org_id] = result["sessions_anchored"]
    return ran
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scheduler.py -v`
Expected: all PASS (existing 5 scheduler tests + the new one).

- [ ] **Step 5: Wire the tick into the app startup**

Read how `run_due_schedules` is currently invoked from the app's startup/background-tick wiring
(search `grep -rn "run_due_schedules" teluvane/` — likely in `teluvane/ingest.py`'s app-startup
APScheduler setup). Add `run_due_anchors` as a sibling job on the same scheduler instance, at a
separate, longer interval (anchoring doesn't need per-minute granularity like audit scheduling
does — every 15-60 minutes is more than enough given anchoring's own skip-if-unchanged check
makes extra ticks cheap regardless). The exact `AnchorClient` instance passed in should be built
once at startup from `ANCHOR_RPC_URL`/`ANCHOR_CONTRACT_ADDRESS`/`ANCHOR_PRIVATE_KEY` env vars
(Task 6 defines these), matching how the app already builds its one shared `Store`/pool at
startup rather than per-request.

- [ ] **Step 6: Commit**

```bash
git add teluvane/scheduler.py tests/test_scheduler.py
git commit -m "feat: add scheduled batch anchoring for Pro-plan orgs"
```

---

### Task 6: Wallet key handling (env, encrypted, redacted from logs)

**Files:**
- Modify: `teluvane/logging_filter.py`
- Modify: `.env.example`
- Test: `tests/test_logging_filter.py` (add case)

**Interfaces:**
- Consumes: `teluvane/crypto.py`'s existing `encrypt`/`decrypt` (Fernet, keyed by
  `TELUVANE_SECRET_KEY`) — the anchoring hot-wallet private key is stored encrypted the same
  way BYOK Anthropic keys already are, no new secret-storage mechanism.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_logging_filter.py` (match its existing test style):
```python
def test_redacts_avalanche_private_keys(caplog):
    import logging
    install_redaction()
    logging.getLogger().warning("wallet key: 0x" + "a" * 64)
    assert "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" not in caplog.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_logging_filter.py -k avalanche -v`
Expected: FAIL (the raw 64-hex-char key appears unredacted in `caplog.text`).

- [ ] **Step 3: Add the pattern**

In `teluvane/logging_filter.py`, add to `_PATTERNS`:
```python
    re.compile(r"0x[0-9a-fA-F]{64}"),   # EVM private keys (Avalanche anchoring hot wallet)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_logging_filter.py -v`
Expected: all PASS.

- [ ] **Step 5: Document the new env vars**

In `.env.example`, add (read the file first to match its existing comment style):
```bash
# Avalanche C-Chain anchoring (Plan 1: chain-tip anchoring). Leave ANCHOR_ENABLED unset/false
# to run with anchoring off -- the rest of the product works identically either way.
ANCHOR_ENABLED=false
ANCHOR_RPC_URL=https://api.avax-test.network/ext/bc/C/rpc
ANCHOR_CONTRACT_ADDRESS=
ANCHOR_PRIVATE_KEY_ENCRYPTED=
```

- [ ] **Step 6: Commit**

```bash
git add teluvane/logging_filter.py tests/test_logging_filter.py .env.example
git commit -m "feat: redact Avalanche wallet keys from logs, document anchoring env vars"
```

---

### Task 7: Public verify endpoint + evidence pack section

**Files:**
- Modify: `teluvane/ingest.py`
- Modify: `teluvane/evidence.py`
- Test: `tests/test_api.py` (add cases), `tests/test_evidence.py` (add cases)

**Interfaces:**
- Produces: `GET /verify/onchain/{session_id}?org_id=...` — **no auth dependency**, unlike every
  other session-scoped endpoint in `ingest.py`. This is deliberate (spec §2, §6): the entire
  point is that a stranger with no TELUVANE account can check a session's integrity. `org_id`
  is a required query param here specifically because there's no `current_org` JWT/API-key
  dependency to derive it from.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py` (match its existing FastAPI `TestClient` style):
```python
def test_verify_onchain_reports_anchored_and_intact(client, store, monkeypatch):
    org_id = "org-verify-test"
    store.append(org_id, Event(agent_id="a1", session_id="s1", kind="tool_call"))
    tip_seq, tip_hash = store.session_tip(org_id, "s1")
    store.add_anchor(org_id, "s1", batch_id="b1", tip_seq=tip_seq, tip_hash=tip_hash,
                     merkle_proof=[], merkle_root=tip_hash, tx_hash="0xabc", block_number=1)
    resp = client.get(f"/verify/onchain/s1?org_id={org_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["chain_intact"] is True
    assert body["anchored"] is True
    assert body["tx_hash"] == "0xabc"

def test_verify_onchain_reports_not_anchored_when_no_anchor_exists(client, store):
    org_id = "org-verify-test-2"
    store.append(org_id, Event(agent_id="a1", session_id="s1", kind="tool_call"))
    resp = client.get(f"/verify/onchain/s1?org_id={org_id}")
    assert resp.status_code == 200
    assert resp.json() == {"chain_intact": True, "anchored": False, "tx_hash": None,
                           "block_number": None, "merkle_root": None}

def test_verify_onchain_requires_no_authentication(client):
    # No Authorization header, no API key -- this is the whole point of the endpoint.
    resp = client.get("/verify/onchain/nonexistent-session?org_id=nonexistent-org")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -k verify_onchain -v`
Expected: FAIL with 404 (route doesn't exist yet).

- [ ] **Step 3: Add the endpoint**

In `teluvane/ingest.py`, near the existing `@app.get("/verify")` (no-auth-vs-auth note: the
*existing* `/verify` requires `current_org` via JWT/API key; this new one deliberately does
not, so place it nearby but do not reuse that route):
```python
@app.get("/verify/onchain/{session_id}")
def verify_onchain(session_id: str, org_id: str) -> dict:
    chain_intact = store.verify_chain(org_id, session_id)
    anchor = store.latest_anchor(org_id, session_id)
    if anchor is None:
        return {"chain_intact": chain_intact, "anchored": False, "tx_hash": None,
                "block_number": None, "merkle_root": None}
    return {"chain_intact": chain_intact, "anchored": True, "tx_hash": anchor["tx_hash"],
            "block_number": anchor["block_number"], "merkle_root": anchor["merkle_root"]}
```

Note this v1 endpoint checks `chain_intact` against our own DB (same as the existing `/verify`)
and separately reports the anchor's existence/tx info -- it does NOT yet re-fetch the on-chain
root from the contract and cross-check the Merkle proof server-side (that's a stronger
"independently verifiable" claim than "trust our DB, but also here's a receipt"). Track that
gap explicitly: a Task 8 (not written here -- add to the ROADMAP if picked up) would have this
endpoint call `AnchorClient.get_anchored_logs` and `verify_merkle_proof` to check the proof
on-chain server-side, and/or the endpoint's response could include the raw proof so a client can
independently re-verify it without trusting this endpoint either. Ship the receipt-reporting
version first since it's still strictly more verifiable than today (a tx hash and block number
are independently checkable on Snowtrace by anyone right now), and note the stronger version as
a fast-follow rather than blocking this plan on it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -k verify_onchain -v`
Expected: PASS, all 3.

- [ ] **Step 5: Add the evidence-pack section**

In `teluvane/evidence.py`, extend `build_evidence_pack` and `_render_html` to accept an optional
`anchor: dict | None` parameter and, when present, render a section with the tx hash, a
Snowtrace link (`f"https://snowtrace.io/tx/{anchor['tx_hash']}"` for mainnet, or the Fuji
explorer's equivalent path when `chain_id` indicates testnet), and one sentence explaining what
it means. Wire `teluvane/ingest.py`'s `/evidence/{session_id}` and `/evidence/{session_id}/pdf`
handlers to pass `store.latest_anchor(org_id, session_id)` through. Add a
`tests/test_evidence.py` case asserting the tx hash string appears in the rendered HTML when an
anchor is present, and that the section is simply absent (not an empty/broken block) when it
isn't -- read `tests/test_evidence.py`'s existing style first to match it.

- [ ] **Step 6: Run the full test suite**

Run: `DATABASE_URL="${TEST_DATABASE_URL:-postgresql://localhost:5432/teluvane_test}" pytest -v`
Expected: all tests PASS, including everything from Tasks 1-6 plus the pre-existing suite.

- [ ] **Step 7: Commit**

```bash
git add teluvane/ingest.py teluvane/evidence.py tests/test_api.py tests/test_evidence.py
git commit -m "feat: add public onchain verify endpoint and evidence pack anchor section"
```

---

### Task 8: Fuji testnet deployment + manual live verification

**Files:**
- Create: `scripts/deploy_anchor_registry.py`
- Modify: `DEPLOY.md`

**Interfaces:**
- None consumed from other tasks besides `teluvane/anchor.py`'s `_compiled()` helper (may need
  to be exposed, not prefixed `_`, if this script imports it directly rather than duplicating
  the compile step -- prefer exposing it).

- [ ] **Step 1: Write the deploy script**

Create `scripts/deploy_anchor_registry.py`: a small standalone script (not part of the pytest
suite -- this genuinely touches a real network) that reads `ANCHOR_RPC_URL` and a plaintext
deployer private key from the environment (never committed, never the same key as the
production anchoring hot wallet -- deployment and day-to-day anchoring should be different keys
so the deployer key can be put away after this one-time step), deploys
`TeluvaneAnchorRegistry.sol` via the same `_compiled()` path Task 3 already wrote, and prints
the deployed contract address.

- [ ] **Step 2: Deploy to Fuji testnet manually**

Run (with a Fuji-funded deployer key set locally, never committed):
```bash
ANCHOR_RPC_URL=https://api.avax-test.network/ext/bc/C/rpc python scripts/deploy_anchor_registry.py
```
Expected: prints a `0x...` contract address. Record it for Step 3.

- [ ] **Step 3: Manual end-to-end check against Fuji**

With `ANCHOR_ENABLED=true`, `ANCHOR_RPC_URL` set to the Fuji endpoint above, and
`ANCHOR_CONTRACT_ADDRESS` set to the Step 2 address, run the app locally, seed a session (the
existing `/demo/seed` endpoint), trigger `run_anchor_batch` directly (or wait for the scheduler
tick), and confirm: (a) `GET /verify/onchain/{session_id}` reports `anchored: true` with a real
`tx_hash`, (b) that tx hash resolves on Fuji's block explorer
(`https://testnet.snowtrace.io/tx/{tx_hash}`) and shows an `Anchored` event log.

- [ ] **Step 4: Document mainnet deployment in `DEPLOY.md`**

Add a section to `DEPLOY.md` (matching its existing per-service structure) covering: deploying
`TeluvaneAnchorRegistry` to Avalanche C-Chain mainnet the same way, funding the anchoring hot
wallet with a small AVAX balance (not the deployer key), encrypting the hot wallet's private key
with `teluvane/crypto.py encrypt()` before setting `ANCHOR_PRIVATE_KEY_ENCRYPTED`, and setting
`ANCHOR_ENABLED=true` only once all of Tasks 1-7 are deployed and this manual Fuji check has
passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/deploy_anchor_registry.py DEPLOY.md
git commit -m "docs: add Avalanche anchor registry deployment script and instructions"
```

---

## Self-Review

**Spec coverage:** Tasks 1-7 implement spec §4-§9 in full (Merkle helpers, data model, anchoring
flow, verification flow, API surface, contract, hot-wallet hardening). Task 8 operationalizes
deployment. Spec §10 (grant application) and §13 (ERC-8004) are deliberately out of this plan's
scope -- see the ROADMAP's Plan 2/Plan 3.

**Placeholder scan:** none -- every task has a real failing test, real minimal implementation,
and a real verification command.

**Type/pattern consistency:** every new `Store` method follows the existing `org_id`-first,
`_assert_scoped`-guarded pattern (Task 2). `AnchorClient` takes an injected provider the same
way `run_lens` takes an injected `llm` (Task 3, matches `tribunal.py`'s existing testability
pattern). The new public endpoint is the *only* session-scoped route in `ingest.py` without a
`current_org` dependency -- called out explicitly in Task 7 so a future reader doesn't mistake
it for an oversight.

**Known gap carried forward on purpose:** Task 7's `/verify/onchain` endpoint reports anchor
receipts but doesn't yet re-derive the on-chain root server-side to cross-check the stored
Merkle proof -- flagged inline as a fast-follow, not silently dropped.
