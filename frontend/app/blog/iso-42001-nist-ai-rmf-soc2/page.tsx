// frontend/app/blog/iso-42001-nist-ai-rmf-soc2/page.tsx
import type { Metadata } from "next";
import ArticleLayout, { proseStyles } from "@/components/blog/ArticleLayout";
import { blogPosts } from "@/lib/blogPosts";

const post = blogPosts.find((p) => p.slug === "iso-42001-nist-ai-rmf-soc2")!;

export const metadata: Metadata = {
  title: `${post.title}: TELUVANE`,
  description: post.description,
};

export default function Post() {
  return (
    <ArticleLayout title={post.title} description={post.description} date={post.date}>
      <p style={proseStyles.p}>
        &quot;What compliance framework do we need?&quot; usually gets answered by whoever is
        asking you for it, a customer&apos;s security questionnaire, an enterprise procurement
        team, or a regulator. Three names come up most often for teams running AI agents: ISO
        42001, NIST AI RMF, and SOC 2. They&apos;re not interchangeable, and they&apos;re not
        competing with each other, they answer different questions.
      </p>

      <h2 style={proseStyles.h2}>ISO 42001: do you manage AI responsibly, as an organization?</h2>
      <p style={proseStyles.p}>
        ISO/IEC 42001 is a certifiable standard for an AI management system, the organizational
        processes around how you develop, deploy, and monitor AI systems. It&apos;s closer in
        spirit to ISO 27001 for information security than to a technical checklist: an external
        auditor can certify that your organization has the governance processes ISO 42001
        requires. Enterprise customers increasingly ask for this certification the same way they
        ask for SOC 2, as a signal that AI risk is being managed, not improvised.
      </p>

      <h2 style={proseStyles.h2}>NIST AI RMF: a risk framework, not a certification</h2>
      <p style={proseStyles.p}>
        The NIST AI Risk Management Framework is voluntary guidance from the U.S. National
        Institute of Standards and Technology. There&apos;s nothing to get &quot;certified&quot;
        against, it&apos;s a structured way to think about identifying, measuring, and managing
        AI risk (organized around functions like Govern, Map, Measure, and Manage). U.S.
        government contractors and vendors selling into regulated U.S. industries encounter this
        one most, either directly or because a customer has adopted it internally.
      </p>

      <h2 style={proseStyles.h2}>SOC 2: does your service organization have good controls?</h2>
      <p style={proseStyles.p}>
        SOC 2 predates the current wave of AI regulation, it&apos;s a general trust-services
        audit (security, availability, confidentiality, and related criteria) that most B2B SaaS
        companies already encounter in vendor security reviews. It&apos;s not AI-specific, but if
        your AI agent touches customer data or makes decisions inside a product you sell to
        other businesses, your SOC 2 auditor will ask about it, because agent behavior is now
        part of your service&apos;s control environment.
      </p>

      <h2 style={proseStyles.h2}>Where audit logs fit into all three</h2>
      <p style={proseStyles.p}>
        Every one of these frameworks, in different language, asks the same underlying question
        about an AI system: can you show what it actually did, and can you show that record is
        trustworthy? ISO 42001 asks it as part of operational monitoring. NIST AI RMF asks it
        under the Measure and Manage functions. SOC 2 asks it as part of your logging and
        monitoring controls. A single tamper-evident record of agent actions, mapped against
        each framework&apos;s specific requirements, is what turns &quot;we think the agent
        behaved correctly&quot; into something an auditor can check.
      </p>

      <h2 style={proseStyles.h2}>Picking one</h2>
      <p style={proseStyles.p}>
        In practice, the framework you need is usually the one your customer, investor, or
        regulator is asking about, not the one that sounds most rigorous. If nobody&apos;s asked
        yet, start with whichever is native to your market: SOC 2 for U.S. B2B SaaS, ISO 42001
        for anyone selling into Europe or dealing with enterprise procurement globally, NIST AI
        RMF if you sell to U.S. government or regulated industries.
      </p>
    </ArticleLayout>
  );
}
