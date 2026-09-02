"use client";
import { Suspense, useEffect, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useSession } from "@/lib/useSession";
import { apiFetch } from "@/lib/api";
import { getSupabase } from "@/lib/supabase";
import TopNav from "@/components/TopNav";

type Plan = { plan: "free" | "starter" | "pro" | string };
type Usage = { hosted_audits_used: number; limit: number };

export default function BillingPage() {
  return (
    <Suspense fallback={null}>
      <BillingPageInner />
    </Suspense>
  );
}

function BillingPageInner() {
  const { token, loading: sessionLoading } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [justUpgraded] = useState(() => searchParams.get("upgraded") === "true");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [busy, setBusy] = useState<"" | "checkout" | "portal">("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { if (!sessionLoading && !token) router.push("/login"); }, [sessionLoading, token, router]);
  useEffect(() => { if (justUpgraded) router.replace("/app/billing"); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const [p, u] = await Promise.all([
        apiFetch<Plan>("/billing/plan", { token }),
        apiFetch<Usage>("/billing/usage", { token }),
      ]);
      setPlan(p);
      setUsage(u);
    } catch (e) { setErr(String(e)); }
    finally { setLoading(false); }
  }, [token]);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    getSupabase().auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
  }, []);

  async function upgrade(plan: "starter" | "pro") {
    if (!token || !email) return;
    setErr(null); setBusy("checkout");
    try {
      const r = await apiFetch<{ url: string }>("/billing/checkout", { token, method: "POST", body: { email, plan } });
      window.location.href = r.url;
    } catch (e) { setErr(String(e)); setBusy(""); }
  }

  async function manage() {
    if (!token) return;
    setErr(null); setBusy("portal");
    try {
      const r = await apiFetch<{ url: string }>("/billing/portal", { token, method: "POST" });
      window.location.href = r.url;
    } catch (e) { setErr(String(e)); setBusy(""); }
  }

  const isStarter = plan?.plan === "starter";
  const isPro = plan?.plan === "pro";
  const pct = usage && usage.limit > 0 ? Math.min(100, Math.round((usage.hosted_audits_used / usage.limit) * 100)) : 0;

  return (
    <>
      <TopNav />
      <main id="main-content" tabIndex={-1} className="page">
        <p className="eyebrow">Workspace</p>
        <h1 style={{ marginBottom: 6 }}>Billing</h1>
        <p className="muted small">
          Free runs the offline detector. Starter and Pro add live Claude tribunal audits on our
          hosted key, metered per month, on top of whatever you get from your own BYOK key. Pro
          also adds scheduled runs, custom policy rules, and on-chain session anchoring.
        </p>

        {justUpgraded && (
          <div className="notice" style={{ borderStyle: "solid", borderColor: "#4caf74", color: "#1a1714", marginBottom: 18 }}>
            Thanks for upgrading. Your plan will update in a moment.
          </div>
        )}

        <div className="card" style={{ marginTop: 18, padding: 24 }}>
          {loading ? <p className="empty">Loading your plan…</p> : (
            <>
              <div className="row" style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                <span className="label" style={{ margin: 0 }}>Plan</span>
                <span className="plan-tag">{plan === null ? (err ? "unreachable" : "checking…") : plan.plan}</span>
              </div>

              {usage && (
                <div style={{ marginBottom: isPro || isStarter ? 20 : 0 }}>
                  <div className="label" style={{ marginBottom: 6 }}>
                    Hosted tribunal audits this month: {usage.hosted_audits_used} / {usage.limit}
                  </div>
                  <div className="meter"><div className="meter-fill" style={{ width: `${pct}%` }} /></div>
                </div>
              )}

              <div className="btn-row" style={{ marginTop: 20 }}>
                {plan?.plan === "free" && (
                  <button className="btn btn-ghost" style={{ width: "auto" }} onClick={() => upgrade("starter")} disabled={!email || busy === "checkout"}>
                    {busy === "checkout" ? "Redirecting…" : "Upgrade to Starter"}
                  </button>
                )}
                {!isPro && (
                  <button className="btn btn-primary" style={{ width: "auto" }} onClick={() => upgrade("pro")} disabled={!email || busy === "checkout"}>
                    {busy === "checkout" ? "Redirecting…" : "Upgrade to Pro"}
                  </button>
                )}
                {(isPro || isStarter) && (
                  <button className="btn btn-ghost" onClick={manage} disabled={busy === "portal"}>
                    {busy === "portal" ? "Redirecting…" : "Manage subscription"}
                  </button>
                )}
              </div>
              {err && <p className="error">{err}</p>}
            </>
          )}
        </div>

        {!isPro && (
          <p className="notice">
            Prefer to skip metering entirely? Add your own Anthropic key on the{" "}
            <a href="/app/settings">Settings</a> page and every plan runs unlimited live audits.
          </p>
        )}
      </main>
    </>
  );
}
