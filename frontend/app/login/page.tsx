"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabase, setRememberMe } from "@/lib/supabase";

export default function LoginPage() {
  const sb = getSupabase();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "signup" | "reset">("login");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [remember, setRemember] = useState(true);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setRememberMe(remember);
    setErr(null);
    setBusy(true);
    // Wrapped in try/finally: signInWithPassword/signUp can throw (network error, bad env
    // config) instead of resolving with `{ error }` — without this the button got stuck
    // showing "…" forever since setBusy(false) was never reached.
    try {
      // Call directly on sb.auth — aliasing the method drops its `this` (the client then reads
      // this.fetch off undefined).
      if (mode === "reset") {
        const { error } = await sb.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/auth/reset`,
        });
        if (error) return setErr(error.message);
        setSent(true);
      } else if (mode === "login") {
        const { error } = await sb.auth.signInWithPassword({ email, password });
        if (error) return setErr(error.message);
        router.push("/app");
      } else {
        const { data, error } = await sb.auth.signUp({
          email, password,
          options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
        });
        if (error) return setErr(error.message);
        if (!data.session) { setSent(true); return; }   // confirmation required: email sent
        router.push("/app");                              // confirmation disabled: straight in
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <main id="main-content" tabIndex={-1} className="center-screen">
        <div className="card auth-card">
          <div className="brand" style={{ marginBottom: 16 }}><span className="mark">T</span> TELUVANE</div>
          <h1 style={{ marginBottom: 8 }}>Check your inbox</h1>
          <p className="muted small" style={{ marginBottom: 20 }}>
            {mode === "reset" ? (
              <>We sent a password reset link to <strong>{email}</strong>. Click it to choose a new password.</>
            ) : (
              <>We sent a confirmation link to <strong>{email}</strong>. Click it to activate your
              account, then you&rsquo;ll be signed in automatically.</>
            )}
          </p>
          <button className="btn btn-ghost" onClick={() => { setSent(false); setMode("login"); }}>
            Back to log in
          </button>
        </div>
      </main>
    );
  }

  return (
    <main id="main-content" tabIndex={-1} className="center-screen">
      <div className="card auth-card">
        <div className="brand" style={{ marginBottom: 16 }}>
          <span className="mark">T</span> TELUVANE
        </div>
        <p className="eyebrow" style={{ marginBottom: 18 }}>AI agent accountability</p>
        <h1 style={{ marginBottom: 4 }}>
          {mode === "login" ? "Welcome back" : mode === "signup" ? "Create your account" : "Reset your password"}
        </h1>
        <p className="muted small" style={{ marginBottom: 24 }}>
          {mode === "login"
            ? "Log in to your workspace."
            : mode === "signup"
            ? "Start auditing your AI agents in minutes."
            : "We'll email you a link to set a new password."}
        </p>

        <form onSubmit={submit}>
          <div className="field">
            <label className="label">Email</label>
            <input className="input" type="email" autoComplete="email" placeholder="you@company.com"
                   value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
          </div>
          {mode !== "reset" && (
            <div className="field">
              <label className="label">Password</label>
              <input className="input" type="password"
                     autoComplete={mode === "login" ? "current-password" : "new-password"}
                     placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required />
            </div>
          )}
          {mode !== "reset" && (
            <div className="field" style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 15 }}>
              <input id="remember-me" type="checkbox" checked={remember}
                     onChange={e => setRemember(e.target.checked)} />
              <label htmlFor="remember-me" className="small muted" style={{ margin: 0 }}>
                Remember me on this device
              </label>
            </div>
          )}
          {mode === "login" && (
            <p className="small" style={{ marginBottom: 15, textAlign: "right" }}>
              <button className="btn-link" type="button" style={{ fontSize: "0.85rem" }}
                      onClick={() => { setErr(null); setMode("reset"); }}>
                Forgot password?
              </button>
            </p>
          )}
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "…" : mode === "login" ? "Log in" : mode === "signup" ? "Sign up" : "Send reset link"}
          </button>
        </form>

        {err && <p className="error" role="alert" aria-live="polite">{err}</p>}

        <p className="muted small" style={{ marginTop: 20 }}>
          {mode === "reset" ? (
            <button className="btn-link" type="button" onClick={() => { setErr(null); setMode("login"); }}>
              Back to log in
            </button>
          ) : (
            <>
              {mode === "login" ? "Need an account? " : "Have an account? "}
              <button className="btn-link" type="button"
                      onClick={() => { setErr(null); setMode(mode === "login" ? "signup" : "login"); }}>
                {mode === "login" ? "Sign up" : "Log in"}
              </button>
            </>
          )}
        </p>
      </div>
    </main>
  );
}
