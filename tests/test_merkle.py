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


def test_root_from_proof_reconstructs_built_root():
    for n in (1, 2, 3, 4, 5, 8):
        leaves = [("o", f"s{i}", f"{i:064x}") for i in range(n)]
        root, proofs = merkle.build_tree(leaves)
        for o, s, h in leaves:
            assert merkle.root_from_proof(o, s, h, proofs[(o, s)]) == root


def test_root_from_proof_single_leaf_is_leaf_hash():
    assert (merkle.root_from_proof("o", "s", "aa", [])
            == "0x" + merkle.leaf_hash("o", "s", "aa").hex())


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
