"""Manual Fuji integration check. NOT run in CI. Requires ANCHOR_* env + a funded
signer. Anchors a throwaway batch and reads it back.

  python scripts/anchor_smoke.py

Env: the same ANCHOR_RPC_URL, ANCHOR_CONTRACT_ADDRESS, ANCHOR_SIGNER_PRIVATE_KEY
(plus optional tuning vars) the backend uses. See teluvane/anchor.py chain_config().

The batch is built from a unique throwaway leaf each run (a timestamp goes into
the session id), so the root is never one a real pass would produce and re-runs
do not collide with the contract's AlreadyAnchored guard.
"""
import sys
import time

from teluvane import anchor, anchor_chain, merkle


def main() -> int:
    cfg = anchor.chain_config()
    assert cfg, "ANCHOR_* env not set (need ANCHOR_RPC_URL, ANCHOR_CONTRACT_ADDRESS, ANCHOR_SIGNER_PRIVATE_KEY)"
    print("signer:", anchor_chain.signer_address(cfg),
          "balance:", anchor_chain.balance_avax(cfg), "AVAX")

    session_id = "smoke-session-%d" % int(time.time())
    chain_head = "ab" * 32
    root, _ = merkle.build_tree([("smoke-org", session_id, chain_head)])
    print("root:", root)

    tx = anchor_chain.submit_batch(cfg, root, 1)
    print("tx:", tx)

    for _ in range(30):
        r = anchor_chain.receipt(cfg, tx)
        if r:
            print("mined block", r["block_number"], "status", r["status"])
            assert r["status"] == 1, "anchor tx reverted"
            break
        time.sleep(5)
    else:
        print("tx not mined within ~150s; check the explorer", file=sys.stderr)
        return 1

    ts = anchor_chain.read_anchored_at(cfg, root)
    print("anchoredAt:", ts)
    assert ts > 0, "root not found on chain after mining"
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
