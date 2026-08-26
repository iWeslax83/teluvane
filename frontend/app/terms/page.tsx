// frontend/app/terms/page.tsx
import type { Metadata } from "next";
import Link from "next/link";
import { sectionStyle, headingStyle, bodyStyle } from "@/lib/legalPageStyles";

export const metadata: Metadata = {
  title: "Terms of Service: TELUVANE",
  description: "The terms governing your use of TELUVANE.",
};

export default function TermsPage() {
  return (
    <main id="main-content" tabIndex={-1} style={{ background: "#f4efe6", color: "#1a1714", fontFamily: "system-ui, -apple-system, sans-serif", minHeight: "100dvh" }}>
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "4rem 2rem 6rem" }}>
        <Link href="/" style={{ color: "#2f5266", fontSize: ".9rem", fontWeight: 600, textDecoration: "none" }}>&larr; Back to homepage</Link>
        <h1 style={{ fontSize: "2.2rem", fontWeight: 800, letterSpacing: "-.02em", margin: "1.5rem 0 .5rem" }}>Terms of Service</h1>
        <p style={{ color: "#8a8275", fontSize: ".9rem", marginBottom: "2.5rem" }}>
          Last updated 2026-08-17. This is a plain-language summary of our terms, not legal advice. If you need a legal opinion on these terms, consult qualified counsel.
        </p>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>The service</h2>
          <p style={bodyStyle}>
            TELUVANE is a flight recorder and compliance tribunal for AI agent actions, offered as a hosted service with a managed dashboard, scheduled audits, and priority support.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Your account</h2>
          <p style={bodyStyle}>
            You&apos;re responsible for the security of your account credentials and your API keys, including any Anthropic key you supply under BYOK. You&apos;re responsible for the content of the agent logs you submit for auditing.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Acceptable use</h2>
          <p style={bodyStyle}>
            Don&apos;t use TELUVANE to process data you don&apos;t have the right to process, or to circumvent the usage limits of your plan. We reserve the right to suspend accounts that abuse the service.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Billing</h2>
          <p style={bodyStyle}>
            Paid plans are billed through LemonSqueezy, our merchant of record. Subscriptions renew automatically until cancelled. You can manage or cancel your subscription from the billing page in your dashboard, which links to LemonSqueezy&apos;s customer portal.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>No warranty</h2>
          <p style={bodyStyle}>
            TELUVANE is a technical tool, not legal advice, and does not guarantee regulatory compliance with the EU AI Act or any other framework. The service is provided &quot;as is,&quot; without warranty of any kind, to the maximum extent permitted by law.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Termination</h2>
          <p style={bodyStyle}>
            You can stop using the service and delete your account at any time. We may suspend or terminate accounts that violate these terms.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={headingStyle}>Contact</h2>
          <p style={bodyStyle}>
            TELUVANE is based in Bursa, Türkiye. For questions about these terms, contact us through the dashboard or your account email.
          </p>
        </section>
      </div>
    </main>
  );
}
