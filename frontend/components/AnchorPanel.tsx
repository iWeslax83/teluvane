"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { rootFromProof } from "@/lib/merkle";
import { verifyChain, type ChainEvent } from "@/lib/chainVerify";
import { createPublicClient, http } from "viem";
import { avalancheFuji } from "viem/chains";
import { decideState, type AnchorState } from "@/lib/anchorState";
import { ANCHOR_CONTRACT, ANCHOR_RPC } from "@/lib/anchorConfig";
import AnchorResult from "@/components/AnchorResult";

// The one contract call the browser makes for itself: anchoredAt(bytes32 root)
// returns the block timestamp the root was recorded at, or 0 if it never was.
export const ANCHOR_ABI = [
  {
    type: "function",
    name: "anchoredAt",
    stateMutability: "view",
    inputs: [{ name: "root", type: "bytes32" }],
    outputs: [{ name: "", type: "uint256" }],
  },
] as const;

type AnchorStatus = {
  anchored: boolean;
  org_id: string;
  proof: string[] | null;
  root: string | null;
  status: string;
  tx_hash: string | null;
  block_number: number | null;
  through_seq: number | null;
  total_seq: number;
  head_stored: string | null;
  head_matches: boolean;
  is_public?: boolean;
};

type ContractInfo = {
  chain_id: number;
  contract_address: `0x${string}`;
  explorer_tx_url: string;
  rpc_url: string;
};

type View = {
  state: AnchorState;
  serverStatus: string;
  onchainTs: number;
  block: number | null;
  tx: string | null;
  txUrl: string;
};

export default function AnchorPanel({ token, sessionId }: { token: string; sessionId: string }) {
  const [view, setView] = useState<View | null>(null);
  const [isPublic, setIsPublic] = useState<boolean | null>(null);
  const [publicBusy, setPublicBusy] = useState(false);
  const [publicError, setPublicError] = useState<string | null>(null);

  async function togglePublic(next: boolean) {
    setPublicBusy(true);
    setPublicError(null);
    const previous = isPublic;
    setIsPublic(next);
    try {
      await apiFetch(`/anchor/${encodeURIComponent(sessionId)}/public`, {
        token,
        method: "PUT",
        body: { public: next },
      });
    } catch {
      setIsPublic(previous);
      setPublicError("Could not change the publish setting. Pro plan only.");
    } finally {
      setPublicBusy(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const status = await apiFetch<AnchorStatus>(
          `/anchor/${encodeURIComponent(sessionId)}`,
          { token },
        );
        if (cancelled) return;
        setIsPublic(status.is_public === true);

        const base = {
          serverStatus: status.status ?? "",
          onchainTs: 0,
          block: status.block_number,
          tx: status.tx_hash,
          txUrl: "",
        };

        if (!status.anchored) {
          setView({ ...base, state: { kind: "not-anchored" } });
          return;
        }
        if (!status.root || !Array.isArray(status.proof)) {
          setView({ ...base, state: { kind: "proof-missing" } });
          return;
        }

        const contract = await apiFetch<ContractInfo>("/anchor/contract", { token });
        const events = await apiFetch<ChainEvent[]>(
          `/anchor/${encodeURIComponent(sessionId)}/canonical`,
          { token },
        );
        if (cancelled) return;

        const chain = await verifyChain(events);
        const localRoot = await rootFromProof(
          status.org_id,
          sessionId,
          status.head_stored ?? "",
          status.proof,
        );
        if (cancelled) return;

        // The API's chain metadata is only usable if it is talking about the
        // chain this build reads. Anything else is an error, never "verified".
        if (contract.chain_id !== avalancheFuji.id) {
          setView({ ...base, state: { kind: "rpc-unreachable" } });
          return;
        }
        // Pinned at build time where available; the API's address is only a
        // fallback, and its rpc_url is never used.
        const address = (ANCHOR_CONTRACT ?? contract.contract_address) as
          | `0x${string}`
          | undefined;
        if (!address) {
          setView({ ...base, state: { kind: "unpinned" } });
          return;
        }

        let onchain: bigint | null;
        try {
          const client = createPublicClient({
            chain: avalancheFuji,
            transport: http(ANCHOR_RPC || undefined),
          });
          onchain = (await client.readContract({
            address,
            abi: ANCHOR_ABI,
            functionName: "anchoredAt",
            args: [status.root as `0x${string}`],
          })) as bigint;
        } catch {
          onchain = null;
        }
        if (cancelled) return;

        const state = decideState({
          anchored: status.anchored,
          root: status.root,
          proof: status.proof,
          serverStatus: status.status,
          headStored: status.head_stored,
          headMatches: status.head_matches,
          chainOk: chain.ok,
          chainHead: chain.head,
          localRoot,
          onchain,
        });

        setView({
          ...base,
          state,
          onchainTs: onchain !== null && onchain > BigInt(0) ? Number(onchain) : 0,
          txUrl: (contract.explorer_tx_url || "") + (status.tx_hash ?? ""),
        });
      } catch {
        if (!cancelled) {
          setView({
            state: { kind: "rpc-unreachable" },
            serverStatus: "",
            onchainTs: 0,
            block: null,
            tx: null,
            txUrl: "",
          });
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, sessionId]);

  return (
    <section aria-label="On-chain anchor" style={{ margin: "1.5rem 0" }}>
      <p
        style={{
          fontSize: 12,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: "#666",
          margin: "0 0 6px",
        }}
      >
        {view?.state.kind === "unpinned"
          ? "Anchor status, as reported by TELUVANE"
          : "Independent check, read from Avalanche"}
      </p>

      {view === null ? (
        <p style={{ margin: 0, color: "#666" }}>Checking Avalanche Fuji&hellip;</p>
      ) : (
        <AnchorResult
          state={view.state}
          onchainTs={view.onchainTs}
          block={view.block}
          tx={view.tx}
          txUrl={view.txUrl}
        />
      )}

      {view?.serverStatus && (
        <p style={{ fontSize: 12, color: "#888", margin: "6px 0 0" }}>
          TELUVANE&apos;s check: {view.serverStatus}
        </p>
      )}

      {isPublic !== null && (
        <>
          <label
            style={{
              display: "flex",
              alignItems: "baseline",
              gap: 8,
              margin: "10px 0 0",
              fontSize: 14,
              lineHeight: 1.55,
            }}
          >
            <input
              type="checkbox"
              checked={isPublic}
              disabled={publicBusy}
              onChange={(e) => togglePublic(e.target.checked)}
            />
            <span>
              Publish this session for public verification. Anyone with the session id
              can then read its full event log on the /verify page.
            </span>
          </label>
          {publicError && (
            <p style={{ fontSize: 12, color: "#b4451f", margin: "4px 0 0" }}>{publicError}</p>
          )}
        </>
      )}
    </section>
  );
}
