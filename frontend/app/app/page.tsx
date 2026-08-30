"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/useSession";
import { apiFetch, apiFetchBlob } from "@/lib/api";
import { useConfirm } from "@/lib/useConfirm";
import TopNav from "@/components/TopNav";
import AnchorPanel from "@/components/AnchorPanel";
import { DOT, anchorRowKind } from "@/lib/anchorState";

type Event = { seq: number; session_id: string; kind: string; tool?: string; intent: string };
type Verdict = { rule_id: string; severity: string; rationale: string };
type SessionRow = { session_id: string; events: number; last_ts: string; anchor?: string };

const ANCHOR_LABEL: Record<string, string> = {
  mined: "anchored", failed: "anchor failed", submitted: "anchoring", pending: "anchoring",
};

const PAGE_SIZE = 25;

export default function AppPage() {
  const { token, loading } = useSession();
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sessionsLimit, setSessionsLimit] = useState(PAGE_SIZE);
  const [hasMore, setHasMore] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [events, setEvents] = useState<Event[]>([]);
  const [verdicts, setVerdicts] = useState<Verdict[]>([]);
  const [chain, setChain] = useState<boolean | null>(null);
  const [busy, setBusy] = useState<"" | "load" | "audit" | "demo" | "pdf">("");
  const [err, setErr] = useState<string | null>(null);
  const confirm = useConfirm();

  useEffect(() => { if (!loading && !token) router.push("/login"); }, [loading, token, router]);

  // Debounce: only refetch 300ms after the user stops typing, and reset to the first page.
  useEffect(() => {
    const t = setTimeout(() => { setDebouncedSearch(search); setSessionsLimit(PAGE_SIZE); }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const loadSessions = useCallback(async () => {
    if (!token) return;
    try {
      const params = new URLSearchParams({ limit: String(sessionsLimit) });
      if (debouncedSearch) params.set("q", debouncedSearch);
      const rows = await apiFetch(`/sessions?${params}`, { token }) as SessionRow[];
      setSessions(rows);
      setHasMore(rows.length === sessionsLimit);
    } catch (e) { setErr(String(e)); }
  }, [token, debouncedSearch, sessionsLimit]);
  useEffect(() => { loadSessions(); }, [loadSessions]);

  const load = useCallback(async (sid?: string) => {
    const id = sid ?? sessionId;
    if (!token || !id) return;
    setSessionId(id); setErr(null); setBusy("load"); setVerdicts([]);
    try {
      setEvents(await apiFetch(`/events?session_id=${encodeURIComponent(id)}`, { token }));
      const v = await apiFetch(`/verify?session_id=${encodeURIComponent(id)}`, { token }) as { chain_intact: boolean };
      setChain(v.chain_intact);
    } catch (e) { setErr(String(e)); } finally { setBusy(""); }
  }, [token, sessionId]);

  async function audit() {
    if (!token || !sessionId) return;
    setErr(null); setBusy("audit");
    try {
      const v = await apiFetch(`/audit/${encodeURIComponent(sessionId)}`, { token, method: "POST" }) as Verdict[];
      setVerdicts(v);
      confirm.show(v.length ? `Audit complete: ${v.length} verdict${v.length === 1 ? "" : "s"}` : "Audit complete: no violations");
    } catch (e) { setErr(String(e)); } finally { setBusy(""); }
  }

  async function seedDemo() {
    if (!token) return;
    setErr(null); setBusy("demo");
    try {
      const r = await apiFetch("/demo/seed", { token, method: "POST" }) as { session_id: string };
      await loadSessions();
      await load(r.session_id);
    } catch (e) { setErr(String(e)); } finally { setBusy(""); }
  }

  async function openEvidence() {
    if (!token || !sessionId) return;
    try {
      const html = await apiFetch(`/evidence/${encodeURIComponent(sessionId)}`, { token }) as string;
      const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (e) { setErr(String(e)); }
  }

  async function downloadEvidencePdf() {
    if (!token || !sessionId) return;
    setErr(null); setBusy("pdf");
    try {
      const blob = await apiFetchBlob(`/evidence/${encodeURIComponent(sessionId)}/pdf`, { token });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${sessionId}-evidence.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (e) {
      const msg = String(e);
      setErr(msg.includes("402") ? "PDF evidence export is a Pro plan feature." : msg);
    } finally { setBusy(""); }
  }

  if (loading) return <main className="page"><p className="muted">Loading…</p></main>;
  return (
    <>
      <TopNav />
      <main id="main-content" tabIndex={-1} className="page">
        <p className="eyebrow">Workspace</p>
        <h1 style={{ marginBottom: 6 }}>Sessions</h1>
        <p className="muted small">Pick a recorded agent session, verify its hash chain, and run the compliance tribunal.</p>

        {sessions.length === 0 && !debouncedSearch ? (
          <div className="card" style={{ marginTop: 18, padding: 24 }}>
            <p className="small" style={{ marginBottom: 14 }}>
              A session is a recorded stream of an agent&rsquo;s actions (tool calls, messages) that
              TELUVANE hash-chains and audits for policy violations. You don&rsquo;t have any yet.
            </p>
            <button className="btn btn-primary" style={{ width: "auto" }} onClick={seedDemo} disabled={busy === "demo"}>
              {busy === "demo" ? "Seeding…" : "Load a demo session"}
            </button>
          </div>
        ) : (
          <>
            <div className="toolbar">
              <input className="input" placeholder="Search sessions…"
                     value={search} onChange={e => setSearch(e.target.value)} />
              <input className="input" placeholder="…or paste a session id"
                     value={sessionId} onChange={e => setSessionId(e.target.value)} />
              <button className="btn btn-ghost" onClick={() => load()} disabled={!sessionId || busy === "load"}>
                {busy === "load" ? "Loading…" : "Load"}
              </button>
            </div>
            {sessions.length === 0 ? <p className="empty">No sessions match &ldquo;{debouncedSearch}&rdquo;.</p> : (
              <ul className="list">
                {sessions.map(s => (
                  <li key={s.session_id} style={{ cursor: "pointer" }} onClick={() => load(s.session_id)}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                      {s.anchor && s.anchor !== "none" && (
                        <span
                          aria-label={ANCHOR_LABEL[s.anchor] ?? s.anchor}
                          title={ANCHOR_LABEL[s.anchor] ?? s.anchor}
                          style={{
                            flex: "none", width: 9, height: 9, borderRadius: "50%",
                            background: DOT[anchorRowKind(s.anchor)],
                          }}
                        />
                      )}
                      <strong>{s.session_id}</strong> <span className="meta">{s.events} events</span>
                    </span>
                    <span className="meta">{s.session_id === sessionId ? "▶ selected" : "open"}</span>
                  </li>
                ))}
              </ul>
            )}
            {hasMore && (
              <p style={{ marginTop: 12 }}>
                <button className="btn btn-ghost btn-sm" onClick={() => setSessionsLimit(l => l + PAGE_SIZE)}>
                  Load more
                </button>
              </p>
            )}
          </>
        )}

        {err && <p className="error">{err}</p>}

        {sessionId && (
          <>
            <div className="section-title">
              <h2>Session · {sessionId}</h2>
              <div className="btn-row">
                <button className="btn btn-primary btn-sm" style={{ width: "auto" }} onClick={audit} disabled={busy === "audit"}>
                  {busy === "audit" ? "Auditing…" : "Run tribunal audit"}
                </button>
                <button className="btn btn-ghost btn-sm" onClick={openEvidence}>Evidence pack ↗</button>
                <button className="btn btn-ghost btn-sm" onClick={downloadEvidencePdf} disabled={busy === "pdf"}>
                  {busy === "pdf" ? "Preparing PDF…" : "Download PDF"}
                </button>
                {confirm.message && <span className="confirm" aria-live="polite">{confirm.message}</span>}
              </div>
            </div>
            {chain !== null && (
              <p><span className={`badge ${chain ? "ok" : "bad"}`}>{chain ? "chain intact" : "chain TAMPERED"}</span></p>
            )}

            {sessionId && token && <AnchorPanel token={token} sessionId={sessionId} />}

            <div className="section-title"><h2>Events</h2><span className="muted small">{events.length}</span></div>
            {events.length === 0 ? <p className="empty">No events.</p> : (
              <ul className="list">
                {events.map(e => (
                  <li key={e.seq}>
                    <span>#{e.seq} · <strong>{e.kind}</strong>{e.tool ? ` · ${e.tool}` : ""}</span>
                    <span className="meta">{e.intent}</span>
                  </li>
                ))}
              </ul>
            )}

            <div className="section-title"><h2>Verdicts</h2><span className="muted small">{verdicts.length}</span></div>
            {verdicts.length === 0 ? <p className="empty">Run an audit to see verdicts.</p> : (
              <ul className="list">
                {verdicts.map((v, i) => (
                  <li key={i}>
                    <span><strong>{v.rule_id}</strong> <span className={`sev ${v.severity}`}>{v.severity}</span></span>
                    <span className="meta">{v.rationale}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </main>
    </>
  );
}
