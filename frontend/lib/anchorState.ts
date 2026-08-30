// Pure state machine for the on-chain anchor check, shared by AnchorPanel
// (Task 15) and the public verify page (Task 16). Given the API's anchor
// status, a locally recomputed chain head + Merkle root, and the value read
// from anchoredAt(root) on a public Avalanche RPC, it decides which of six
// states to show. No React, no fetch: easy to test in isolation.

export type AnchorStateKind =
  | "not-anchored"
  | "pending"
  | "verified"
  | "mismatch"
  | "rpc-unreachable"
  | "proof-missing";

export type AnchorState =
  | { kind: "not-anchored" }
  | { kind: "pending" }
  | { kind: "verified" }
  | { kind: "mismatch"; why: string }
  | { kind: "rpc-unreachable" }
  | { kind: "proof-missing" };

// Small colored dot next to plain text. No pills (see repo CLAUDE.md).
export const DOT: Record<AnchorStateKind, string> = {
  "not-anchored": "#8a8a8a",
  pending: "#c98a1b",
  verified: "#1f7a3d",
  mismatch: "#b4451f",
  "rpc-unreachable": "#8a8a8a",
  "proof-missing": "#b4451f",
};

export interface DecideInput {
  // Straight from GET /anchor/{session_id}
  anchored: boolean;
  root: string | null;
  proof: unknown;
  serverStatus: string;
  headStored: string | null;
  headMatches: boolean;
  // Recomputed in the browser
  chainOk: boolean;
  chainHead: string | undefined;
  localRoot: string | null;
  // Read from anchoredAt(root) on a public RPC; null means the read failed
  onchain: bigint | null;
}

export function decideState(i: DecideInput): AnchorState {
  if (!i.anchored) return { kind: "not-anchored" };
  if (!i.root || !Array.isArray(i.proof)) return { kind: "proof-missing" };
  if (i.onchain === null) return { kind: "rpc-unreachable" };

  const headOk = i.chainOk && i.chainHead === i.headStored && i.headMatches;
  const rootOk = i.localRoot !== null && i.localRoot === i.root;

  if (headOk && rootOk && i.onchain > BigInt(0)) return { kind: "verified" };
  if (i.serverStatus === "pending" || i.serverStatus === "submitted") return { kind: "pending" };

  const why = i.onchain === BigInt(0)
    ? "root not found on Avalanche"
    : "recomputed hash does not match the anchored root";
  return { kind: "mismatch", why };
}

// Maps the per-row `anchor` field from GET /sessions
// (none|pending|submitted|mined|failed) to a state kind for the DOT map.
export function anchorRowKind(anchor: string | undefined | null): AnchorStateKind {
  switch (anchor) {
    case "mined":
      return "verified";
    case "failed":
      return "mismatch";
    case "submitted":
    case "pending":
      return "pending";
    default:
      return "not-anchored";
  }
}
