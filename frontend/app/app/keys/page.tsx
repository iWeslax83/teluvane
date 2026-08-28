"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/useSession";
import { apiFetch } from "@/lib/api";
import { useConfirm } from "@/lib/useConfirm";
import TopNav from "@/components/TopNav";

type ApiKey = { id: number; name: string; prefix: string; revoked_at: string | null };

export default function KeysPage() {
  const { token, loading: sessionLoading } = useSession();
  const router = useRouter();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [created, setCreated] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";
  const confirm = useConfirm();

  useEffect(() => { if (!sessionLoading && !token) router.push("/login"); }, [sessionLoading, token, router]);

  const refresh = useCallback(async () => {
    if (!token) return;
    try { setKeys(await apiFetch("/keys", { token })); }
    catch (e) { setErr(String(e)); }
    finally { setLoading(false); }
  }, [token]);
  useEffect(() => { refresh(); }, [refresh]);

  async function create() {
    if (!token || !name) return;
    setErr(null);
    try {
      const r = await apiFetch("/keys", { token, method: "POST", body: { name } }) as { key: string };
      setCreated(r.key);
      setName("");
      refresh();
    } catch (e) { setErr(String(e)); }
  }
  async function revoke(id: number) {
    if (!token) return;
    try { await apiFetch(`/keys/${id}`, { token, method: "DELETE" }); refresh(); confirm.show("Key revoked"); }
    catch (e) { setErr(String(e)); }
  }

  return (
    <>
      <TopNav />
      <main id="main-content" tabIndex={-1} className="page">
        <p className="eyebrow">Workspace</p>
        <h1 style={{ marginBottom: 6 }}>API keys</h1>
        <p className="muted small">Use a key as a bearer token so your agents can record events to TELUVANE.</p>

        <div className="toolbar">
          <input className="input" placeholder="key name (e.g. production)"
                 value={name} onChange={e => setName(e.target.value)} />
          <button className="btn btn-primary" style={{ width: "auto" }} onClick={create} disabled={!name}>
            Create key
          </button>
          {confirm.message && <span className="confirm" aria-live="polite">{confirm.message}</span>}
        </div>

        {created && (
          <div className="notice">
            Copy this now, it’s shown only once:&nbsp;<span className="code">{created}</span>
          </div>
        )}
        {err && <p className="error">{err}</p>}

        {loading ? <p className="empty">Loading your API keys…</p> : keys.length === 0 ? <p className="empty">No keys yet.</p> : (
          <ul className="list">
            {keys.map(k => (
              <li key={k.id}>
                <span><span className="code">{k.prefix}…</span> &nbsp;{k.name}</span>
                {k.revoked_at
                  ? <span className="badge bad">revoked</span>
                  : <button className="btn btn-ghost btn-sm" onClick={() => revoke(k.id)}>Revoke</button>}
              </li>
            ))}
          </ul>
        )}

        <div className="section-title"><h2>Record an event</h2></div>
        <p className="muted small">Send agent actions to TELUVANE with your key as a bearer token:</p>
        <pre className="notice" style={{ whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
{`curl -X POST ${apiBase}/events \\
  -H "Authorization: Bearer tv_live_…" \\
  -H "Content-Type: application/json" \\
  -d '{"agent_id":"my-agent","session_id":"sess-1",
       "kind":"tool_call","tool":"send_email",
       "args":{"to":"x@y.com"},"intent":"send report"}'`}
        </pre>
        <p className="muted small">Then open <a href="/app">Sessions</a> to verify the chain and run the tribunal.</p>
      </main>
    </>
  );
}
