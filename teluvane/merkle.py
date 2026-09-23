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
    payload = (
        LEAF_PREFIX
        + org_id.encode("utf-8")
        + b"|"
        + session_id.encode("utf-8")
        + b"|"
        + chain_head_hex.encode("utf-8")
    )
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


def root_from_proof(org_id: str, session_id: str, chain_head_hex: str, proof: list[str]) -> str:
    """Fold the leaf through its proof siblings and return the "0x"-prefixed root
    the proof implies. A single-leaf proof (proof == []) returns the leaf hash."""
    acc = leaf_hash(org_id, session_id, chain_head_hex)
    for sib_hex in proof:
        sib = bytes.fromhex(sib_hex[2:] if sib_hex.startswith("0x") else sib_hex)
        acc = _node(acc, sib)
    return "0x" + acc.hex()


def verify_proof(org_id: str, session_id: str, chain_head_hex: str, proof, root_hex: str) -> bool:
    implied = root_from_proof(org_id, session_id, chain_head_hex, proof)
    return implied == (root_hex if root_hex.startswith("0x") else "0x" + root_hex)
