"use client";
import { useState } from "react";
import { rootFromProof } from "@/lib/merkle";
import { verifyChain, type ChainEvent } from "@/lib/chainVerify";
import { createPublicClient, http } from "viem";
import { avalancheFuji } from "viem/chains";
import { decideState, type AnchorState } from "@/lib/anchorState";
import { ANCHOR_ABI } from "@/components/AnchorPanel";
import AnchorResult from "@/components/AnchorResult";

// Everything runVerification needs. The session-id path gets this straight from
// GET /verify/public/{id}; the evidence-pack path assembles it from the pasted
// JSON. `verify` is the backend's verify_session dict (org_id, status, ...).
type VerifyBundle = {
  session_id: string;
  canonical: ChainEvent[];
  proof: string[];
  chain_head: string | null;
  root: string;
  tx_hash: string | null;
  contract_address?: string;
  explorer_tx_url?: string;
  rpc_url?: string;
  verify: {
    org_id: string;
    status?: string;
    head_stored?: string | null;
    block_number?: number | null;
    [k: string]: unknown;
  };
};

type Method = "session id" | "evidence pack";

type Result = {
  method: Method;
  state: AnchorState;
  onchainTs: number;
  block: number | null;
  tx: string | null;
  txUrl: string;
};

const ACCENT = "#1f4f7a";
const API = process.env.NEXT_PUBLIC_API_URL ?? "";

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "0.6rem 0.7rem",
  fontSize: "0.95rem",
  fontFamily: "inherit",
  border: "1px solid #c9c1b4",
  background: "#fff",
  color: "#1a1714",
};

const buttonStyle: React.CSSProperties = {
  marginTop: "0.6rem",
  padding: "0.55rem 1.1rem",
  fontSize: "0.95rem",
  fontWeight: 600,
  fontFamily: "inherit",
  color: "#fff",
  background: ACCENT,
  border: `1px solid ${ACCENT}`,
  cursor: "pointer",
};

const labelStyle: React.CSSProperties = {
  display: "block",
  fontWeight: 600,
  marginBottom: "0.35rem",
};

async function runVerification(bundle: VerifyBundle, method: Method): Promise<Result> {
  const base = { method, onchainTs: 0, block: null as number | null, tx: null as string | null, txUrl: "" };
  try {
    const chain = await verifyChain(bundle.canonical);
    const anchoredHead = bundle.chain_head ?? bundle.verify.head_stored ?? "";
    const localRoot = await rootFromProof(
      bundle.verify.org_id,
      bundle.session_id,
      anchoredHead,
      bundle.proof ?? [],
    );

    let onchain: bigint | null;
    try {
      if (!bundle.contract_address) throw new Error("no contract address");
      const client = createPublicClient({
        chain: avalancheFuji,
        transport: http(bundle.rpc_url || undefined),
      });
      onchain = (await client.readContract({
        address: bundle.contract_address as `0x${string}`,
        abi: ANCHOR_ABI,
        functionName: "anchoredAt",
        args: [bundle.root as `0x${string}`],
      })) as bigint;
    } catch {
      onchain = null;
    }

    const state = decideState({
      anchored: true,
      root: bundle.root,
      proof: bundle.proof,
      serverStatus: bundle.verify.status ?? "",
      headStored: anchoredHead || null,
      // Recomputed in the browser, not taken from the server: the chain head we
      // just rebuilt from the canonical events must equal the head that was anchored.
      headMatches: chain.ok && chain.head === anchoredHead,
      chainOk: chain.ok,
      chainHead: chain.head,
      localRoot,
      onchain,
    });

    return {
      ...base,
      state,
      onchainTs: onchain !== null && onchain > BigInt(0) ? Number(onchain) : 0,
      block: bundle.verify.block_number ?? null,
      tx: bundle.tx_hash,
      txUrl: (bundle.explorer_tx_url || "") + (bundle.tx_hash ?? ""),
    };
  } catch {
    return { ...base, state: { kind: "rpc-unreachable" } };
  }
}

export default function VerifyClient() {
  const [sessionId, setSessionId] = useState("");
  const [pack, setPack] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  function reset() {
    setError(null);
    setResult(null);
  }

  async function verifyBySessionId() {
    const id = sessionId.trim();
    if (!id || busy) return;
    reset();
    setBusy(true);
    try {
      const res = await fetch(`${API}/verify/public/${encodeURIComponent(id)}`);
      if (!res.ok) {
        setError("No public record for this session id.");
        return;
      }
      const bundle = (await res.json()) as VerifyBundle;
      setResult(await runVerification(bundle, "session id"));
    } catch {
      setError("Could not reach the TELUVANE API to look up this session.");
    } finally {
      setBusy(false);
    }
  }

  async function verifyByPack() {
    if (!pack.trim() || busy) return;
    reset();
    setBusy(true);
    try {
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(pack);
      } catch {
        setError("That is not valid JSON. Paste the evidence pack's JSON export.");
        return;
      }

      // The pack's `json` output carries `anchor` (the verify_session dict). We
      // also need the canonical event list and the Merkle proof to recompute the
      // root offline; packs exported before this feature shipped lack them.
      const anchor = (parsed.anchor ?? {}) as Record<string, unknown>;
      const canonical = (parsed.canonical ?? anchor.canonical) as ChainEvent[] | undefined;
      const proof = (parsed.proof ?? anchor.proof) as string[] | undefined;
      const root = (parsed.root ?? anchor.root) as string | undefined;

      if (!Array.isArray(canonical) || !Array.isArray(proof) || !root) {
        setError(
          "This evidence pack was exported before on-chain anchoring; re-export to verify offline.",
        );
        return;
      }

      const bundle: VerifyBundle = {
        session_id: (parsed.session_id as string) ?? (anchor.session_id as string) ?? "",
        canonical,
        proof,
        chain_head:
          (parsed.chain_head as string) ??
          (anchor.head_stored as string) ??
          null,
        root,
        tx_hash: (parsed.tx_hash as string) ?? (anchor.tx_hash as string) ?? null,
        contract_address:
          (parsed.contract_address as string) ?? (anchor.contract_address as string) ?? undefined,
        explorer_tx_url:
          (parsed.explorer_tx_url as string) ?? (anchor.explorer_tx_url as string) ?? undefined,
        rpc_url: (parsed.rpc_url as string) ?? undefined,
        verify: {
          org_id: (anchor.org_id as string) ?? (parsed.org_id as string) ?? "",
          status: (anchor.status as string) ?? undefined,
          head_stored: (anchor.head_stored as string) ?? null,
          block_number: (anchor.block_number as number) ?? null,
        },
      };
      setResult(await runVerification(bundle, "evidence pack"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ marginTop: "2rem" }}>
      <section style={{ marginBottom: "2.5rem" }}>
        <label htmlFor="verify-session-id" style={labelStyle}>
          Check by session id
        </label>
        <p style={{ margin: "0 0 0.6rem", color: "#5a534a", fontSize: "0.9rem" }}>
          Paste a session id that an organization has published. The check reads
          Avalanche Fuji from your browser.
        </p>
        <input
          id="verify-session-id"
          aria-label="session id"
          value={sessionId}
          onChange={(e) => setSessionId(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") verifyBySessionId();
          }}
          placeholder="session id"
          style={inputStyle}
        />
        <button type="button" onClick={verifyBySessionId} disabled={busy} style={buttonStyle}>
          Verify
        </button>
      </section>

      <section style={{ marginBottom: "2.5rem" }}>
        <label htmlFor="verify-pack" style={labelStyle}>
          Check an exported evidence pack
        </label>
        <p style={{ margin: "0 0 0.6rem", color: "#5a534a", fontSize: "0.9rem" }}>
          Paste the JSON from an evidence pack export. Nothing is uploaded; the
          check runs entirely in your browser.
        </p>
        <textarea
          id="verify-pack"
          aria-label="evidence pack JSON"
          value={pack}
          onChange={(e) => setPack(e.target.value)}
          rows={6}
          placeholder="{ ... }"
          style={{ ...inputStyle, fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", resize: "vertical" }}
        />
        <button type="button" onClick={verifyByPack} disabled={busy} style={buttonStyle}>
          Verify pack
        </button>
      </section>

      <div aria-live="polite">
        {busy && <p style={{ color: "#5a534a" }}>Checking Avalanche Fuji&hellip;</p>}

        {error && (
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              gap: 10,
              border: "1px solid #ddd",
              borderLeftWidth: 3,
              borderLeftColor: "#b4451f",
              padding: "12px 14px",
            }}
          >
            <span
              aria-hidden="true"
              style={{ flex: "none", width: 10, height: 10, borderRadius: "50%", background: "#b4451f", transform: "translateY(1px)" }}
            />
            <div style={{ fontSize: 16, lineHeight: 1.55 }}>{error}</div>
          </div>
        )}

        {result && (
          <>
            <p style={{ margin: "0 0 6px", fontSize: 12, letterSpacing: "0.06em", textTransform: "uppercase", color: "#666" }}>
              Result from the {result.method} you gave
            </p>
            <AnchorResult
              state={result.state}
              onchainTs={result.onchainTs}
              block={result.block}
              tx={result.tx}
              txUrl={result.txUrl}
            />
          </>
        )}
      </div>
    </div>
  );
}
