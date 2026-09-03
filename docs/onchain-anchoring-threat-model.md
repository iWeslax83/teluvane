# SessionAnchorRegistry: threat model and self-review

Written as a lightweight, no-cost stand-in for a paid external audit while `SessionAnchorRegistry.sol`
is still Fuji-only. Revisit before any mainnet deploy or before citing "audited" anywhere.

**Scope:** `contracts/SessionAnchorRegistry.sol` (30 lines) and the off-chain code that calls it
(`teluvane/anchor.py`, `teluvane/anchor_chain.py`).

## Contract itself

```solidity
contract SessionAnchorRegistry {
    address public immutable owner;
    mapping(bytes32 => uint256) public anchoredAt;
    function anchorBatch(bytes32 root, uint256 sessionCount) external {
        if (msg.sender != owner) revert NotOwner();
        if (sessionCount == 0) revert EmptyBatch();
        if (anchoredAt[root] != 0) revert AlreadyAnchored();
        anchoredAt[root] = block.timestamp;
        emit BatchAnchored(root, sessionCount, block.timestamp);
    }
}
```

- **No funds held.** Not payable, never transfers value. There is nothing for an attacker to
  drain; the only assets at risk are write access and data integrity.
- **No re-entrancy surface.** No external calls, no `.call`/`.transfer`/`.send`.
- **No upgradeability.** No proxy, no `delegatecall`, no admin-settable logic. What's deployed is
  what runs, forever. This is a deliberate design choice per the grant pitch and it holds.
- **`owner` is immutable and has no transfer function.** Set once at `constructor()`, never
  changed. This means: (a) no owner-key rotation is possible if the hot wallet key is ever
  compromised or lost, short of redeploying a new contract and updating
  `ANCHOR_CONTRACT_ADDRESS` everywhere; (b) a stolen owner key lets an attacker call
  `anchorBatch` with an arbitrary root, but cannot touch already-anchored roots
  (`AlreadyAnchored` guard) and cannot drain anything. **Accepted risk for Fuji; before mainnet,
  consider adding a two-step `transferOwnership`/`acceptOwnership` pair** (OpenZeppelin's
  `Ownable2Step` pattern) so a compromised or lost key has a recovery path.
- **`anchoredAt[root] != 0` used as a timestamp sentinel, not a security gate.** Slither flags
  this as "dangerous timestamp comparison" (`block.timestamp` can be miner-influenced by a few
  seconds on some chains). Reviewed and accepted: the value is only ever compared to zero to
  detect "not yet anchored," never used for time-window logic, so miner-level timestamp skew
  (seconds) has no effect on correctness.

## Off-chain trust assumptions (what a third party is actually trusting)

1. **The signer's private key is honest.** `ANCHOR_SIGNER_PRIVATE_KEY` is a single hot wallet
   (`teluvane/anchor.py`); whoever holds it can anchor any root they like. A third party
   re-verifying via `/verify/public/{session_id}` is trusting that TELUVANE's server-side Merkle
   build (`teluvane/merkle.py`) faithfully represents the stored event chain, not the on-chain
   write itself. The chain only proves *a* root was committed at a timestamp and never changed
   after; it does not by itself prove the root was built honestly. This is stated correctly in
   `docs/onchain-anchoring.md` but worth restating here as the actual trust boundary.
2. **RPC provider integrity.** `anchor_chain.make_w3()` (after this session's fallback change)
   trusts whichever configured provider answers first. A malicious or compromised RPC endpoint
   could theoretically lie about `anchoredAt()` reads to a browser client that trusts the server's
   relayed answer rather than querying a public explorer directly — mitigated by the existing
   browser-side re-verification (`frontend/lib/chainVerify.ts`) reading straight from chain via
   viem, independent of the API server.
3. **Signer key custody.** `ANCHOR_SIGNER_PRIVATE_KEY` lives in Render env vars (`DEPLOY.md`).
   Standard platform-secret risk (Render account compromise = key compromise); no HSM or
   multi-sig. Acceptable for Fuji-testnet-value funds; revisit key custody (e.g. a dedicated
   signing service or hardware-backed key) before moving real funded operations to mainnet, per
   the grant's own "mainnet-hardened" ask.

## Slither result

One finding (`timestamp` detector, reviewed above as accepted, not a real issue for this usage).
Zero findings in reentrancy, access-control, arithmetic, or unchecked-call categories — the
contract is small enough that Slither's 102 detectors have very little surface to flag.

## Recommendation

This self-review is enough to say "reviewed, no fund-at-risk, main gap is owner-key recovery" in
grant materials. It is **not** a substitute for a paid external audit once real transaction
volume or reputational stakes justify one (i.e. once mainnet is live and the grant's Phase 2
ERC-8004 integration adds a second, more complex contract). Recommend budgeting for one at that
point rather than before.
