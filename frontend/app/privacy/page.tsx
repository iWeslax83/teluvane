// frontend/app/privacy/page.tsx
import type { Metadata } from "next";
import Link from "next/link";
import { sectionStyle, headingStyle, bodyStyle } from "@/lib/legalPageStyles";

export const metadata: Metadata = {
  title: "Privacy Policy: TELUVANE",
  description: "How TELUVANE collects, uses, and protects your data.",
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  return (
    <main id="main-content" tabIndex={-1} style={{ background: "#f4efe6", color: "#1a1714", fontFamily: "system-ui, -apple-system, sans-serif", minHeight: "100dvh" }}>
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "4rem 2rem 6rem" }}>
        <Link href="/" style={{ color: "#2f5266", fontSize: ".9rem", fontWeight: 600, textDecoration: "none" }}>&larr; Back to homepage</Link>
        <h1 style={{ fontSize: "2.2rem", fontWeight: 800, letterSpacing: "-.02em", margin: "1.5rem 0 .5rem" }}>Privacy Policy</h1>
        <p style={{ color: "#8a8275", fontSize: ".9rem", marginBottom: "2.5rem" }}>
          Last updated 2026-08-17. This is a technical description of our current data practices, not legal advice. If you need a legal opinion on this policy, consult qualified counsel.
        </p>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>What we collect</h2>
          <p style={bodyStyle}>
            When you create an account, we collect the email address and password you provide (handled by our authentication provider, Supabase). If you enable BYOK (bring your own key) mode, we store the Anthropic API key you supply so TELUVANE can run live tribunal audits on your behalf. We also store the AI agent action logs you send us for auditing, the API keys TELUVANE issues you for programmatic access, and basic usage counters (how many hosted audits your workspace has run).
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>What we don&apos;t collect</h2>
          <p style={bodyStyle}>
            We don&apos;t store your payment card details. Billing is handled by LemonSqueezy, our merchant of record; LemonSqueezy processes and stores payment information under their own privacy policy.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Third-party processors</h2>
          <p style={bodyStyle}>
            We use Supabase for authentication and database hosting, LemonSqueezy for billing and payment processing, and, if you enable BYOK, Anthropic to run the live tribunal audits using the API key you provide. Each of these processors has its own privacy policy governing the data they handle on our behalf.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>How we use your data</h2>
          <p style={bodyStyle}>
            We use your data to operate the product: authenticating you, running audits against the logs you submit, tracking usage against your plan, and processing billing. We do not sell your data.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Data retention</h2>
          <p style={bodyStyle}>
            We retain your account data and audit logs for as long as your account is active. You can delete your API keys and clear your BYOK key at any time from the dashboard. To request full account deletion, open an issue on our GitHub repository (see Contact below).
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Your rights</h2>
          <p style={bodyStyle}>
            You can access, correct, or delete the data associated with your account by contacting us as described below. If you are located in a jurisdiction with statutory data-protection rights (such as the EU), those rights apply to the extent required by law.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Contact</h2>
          <p style={bodyStyle}>
            TELUVANE is based in Bursa, Türkiye. For privacy questions or data requests, contact us through the dashboard or your account email.
          </p>
        </section>
      </div>
    </main>
  );
}
