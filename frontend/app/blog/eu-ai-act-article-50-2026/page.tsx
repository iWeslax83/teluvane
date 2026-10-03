// frontend/app/blog/eu-ai-act-article-50-2026/page.tsx
import type { Metadata } from "next";
import ArticleLayout, { proseStyles } from "@/components/blog/ArticleLayout";
import { blogPosts } from "@/lib/blogPosts";

const post = blogPosts.find((p) => p.slug === "eu-ai-act-article-50-2026")!;

export const metadata: Metadata = {
  title: `${post.title}: TELUVANE`,
  description: post.description,
  alternates: { canonical: `/blog/${post.slug}` },
  openGraph: {
    type: "article",
    title: post.title,
    description: post.description,
    url: `/blog/${post.slug}`,
    publishedTime: post.date,
    authors: ["Emir Sakarya"],
  },
};

export default function Post() {
  return (
    <ArticleLayout slug={post.slug} title={post.title} description={post.description} date={post.date}>
      <p style={proseStyles.p}>
        If your product uses an AI agent that talks to customers, generates content, or makes
        decisions that affect people, 2026 is the year the EU AI Act starts asking you to prove
        it. Article 50 introduces transparency obligations, chatbot and synthetic-media
        disclosure requirements aimed at making sure people know when they&apos;re interacting
        with an AI system rather than a human.
      </p>

      <h2 style={proseStyles.h2}>What&apos;s actually live in 2026</h2>
      <p style={proseStyles.p}>
        Article 50&apos;s transparency obligations take effect in 2026. In practice, that means
        disclosure requirements for AI-generated or AI-manipulated content, and for systems that
        interact directly with people. The Act&apos;s broader high-risk system obligations,
        the more extensive requirements around risk management, technical documentation, and
        conformity assessment, have been delayed under the Digital Omnibus to December 2027.
      </p>
      <p style={proseStyles.p}>
        That gap matters for planning. Transparency is the near-term requirement; the full
        high-risk compliance regime is the one to prepare for over the next 18 months, not
        scramble for at the deadline.
      </p>

      <h2 style={proseStyles.h2}>Article 15: robustness and cybersecurity</h2>
      <p style={proseStyles.p}>
        Alongside transparency, Article 15 sets robustness and cybersecurity requirements. For an
        AI agent, that increasingly means being able to demonstrate, not just assert, what the
        agent did: which tools it called, what inputs it received, what it produced. A verbal
        assurance that &quot;the agent behaved correctly&quot; isn&apos;t evidence. A log an
        auditor can independently verify is.
      </p>

      <h2 style={proseStyles.h2}>Non-compliance is not a rounding error</h2>
      <p style={proseStyles.p}>
        The maximum fine for non-compliance with EU AI Act obligations is €35M or 7% of global
        annual revenue, whichever is higher. That figure applies to the most serious violations
        (prohibited AI practices), but it sets the tone: this isn&apos;t a framework regulators
        expect you to interpret loosely.
      </p>

      <h2 style={proseStyles.h2}>What this means practically</h2>
      <p style={proseStyles.p}>
        Teams running agents in production need two things well before an audit happens: a
        record of what the agent actually did, and a way to show that record hasn&apos;t been
        altered after the fact. Debugging traces from your observability tool usually cover the
        first part. They rarely cover the second, most logging systems have no mechanism to
        prove a row wasn&apos;t edited or deleted after the incident that made you want to look
        at it.
      </p>
    </ArticleLayout>
  );
}
