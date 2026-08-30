import { DOT, type AnchorState } from "@/lib/anchorState";

// The state -> markup for the on-chain anchor check, shared by AnchorPanel (the
// logged-in dashboard) and VerifyClient (the public /verify page) so the six
// states render identically in both places. Pure: it just draws `state`.

export interface AnchorResultProps {
  state: AnchorState;
  // Only read when state.kind === "verified".
  onchainTs?: number;
  block?: number | null;
  tx?: string | null;
  txUrl?: string;
}

const ACCENT = "#1f4f7a";

export default function AnchorResult({
  state,
  onchainTs = 0,
  block = null,
  tx = null,
  txUrl = "",
}: AnchorResultProps) {
  const kind = state.kind;
  // Only ever link out over https. txUrl is built from an explorer prefix + a tx
  // hash; on the public verify page the prefix can originate from user-pasted
  // JSON, so a "javascript:" or other hostile scheme must never reach an href.
  const safeTxUrl = typeof txUrl === "string" && txUrl.startsWith("https://") ? txUrl : null;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "baseline",
        gap: 10,
        border: `1px solid ${kind === "verified" ? DOT.verified : "#ddd"}`,
        borderLeftWidth: 3,
        borderLeftColor: DOT[kind],
        padding: "12px 14px",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          flex: "none",
          width: 10,
          height: 10,
          borderRadius: "50%",
          background: DOT[kind],
          transform: "translateY(1px)",
        }}
      />
      <div style={{ fontSize: 16, lineHeight: 1.55 }}>
        {state.kind === "not-anchored" && (
          <span>This session has not been anchored on-chain yet.</span>
        )}
        {state.kind === "pending" && (
          <span>Anchor transaction submitted. Waiting for Avalanche to confirm it.</span>
        )}
        {state.kind === "verified" && (
          <span>
            <strong>Verified.</strong> The Merkle root for this session is recorded on
            Avalanche Fuji, timestamped {new Date(onchainTs * 1000).toISOString()}
            {block != null ? `, block ${block}` : ""}.{" "}
            {tx &&
              (safeTxUrl ? (
                <a href={safeTxUrl} target="_blank" rel="noreferrer" style={{ color: ACCENT }}>
                  {tx}
                </a>
              ) : (
                <span>{tx}</span>
              ))}
          </span>
        )}
        {state.kind === "mismatch" && (
          <span>
            <strong>Does not verify.</strong> TELUVANE lists this session as anchored, but
            the independent check does not match: {state.why}.
          </span>
        )}
        {state.kind === "rpc-unreachable" && (
          <span>Could not reach an Avalanche RPC to read the anchor. Try again shortly.</span>
        )}
        {state.kind === "unpinned" && (
          <span>
            Could not independently verify (no pinned contract). This build has no
            contract address to read from Avalanche, so the only thing shown here is
            what the TELUVANE API reports.
          </span>
        )}
        {state.kind === "proof-missing" && (
          <span>
            The anchor record is incomplete (no Merkle proof), so it cannot be checked
            independently.
          </span>
        )}
      </div>
    </div>
  );
}
