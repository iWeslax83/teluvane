// frontend/app/blog/tamper-evident-agent-logs/page.tsx
import type { Metadata } from "next";
import ArticleLayout, { proseStyles } from "@/components/blog/ArticleLayout";
import { blogPosts } from "@/lib/blogPosts";

const post = blogPosts.find((p) => p.slug === "tamper-evident-agent-logs")!;

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
    images: ["/opengraph-image"],
  },
};

export default function Post() {
  return (
    <ArticleLayout slug={post.slug} title={post.title} description={post.description} date={post.date}>
      <p style={proseStyles.p}>
        Most AI agent logging answers &quot;what did the agent do?&quot; A timestamped row says
        the agent called <code>send_email</code> at 14:32:07 with certain arguments. That&apos;s
        useful for debugging. It&apos;s not useful for an audit, because it doesn&apos;t answer
        the harder question: how do you know that row is what actually happened, and not what
        someone edited it to say afterward?
      </p>

      <h2 style={proseStyles.h2}>The gap between logging and evidence</h2>
      <p style={proseStyles.p}>
        A standard database table has no built-in resistance to a row being updated or deleted
        after the fact, by a bug, a well-meaning engineer cleaning up an embarrassing incident,
        or an attacker covering their tracks. If your only proof an agent behaved correctly is a
        row in a table anyone with write access could have changed, that proof doesn&apos;t hold
        up to scrutiny. This is exactly the gap regulators are pointing at when they ask for
        auditable records rather than logs.
      </p>

      <h2 style={proseStyles.h2}>How hash-chaining closes it</h2>
      <p style={proseStyles.p}>
        Hash-chaining is a simple idea borrowed from how blockchains and Git both guarantee
        integrity: each event stores a cryptographic hash of the event before it. Change a
        single byte in an old event, and its hash no longer matches what the next event recorded.
        Every event after the tampered one fails verification the next time anyone reads the
        chain.
      </p>
      <p style={proseStyles.p}>
        Concretely: if you edit event #14 in a 4,471-event session log, re-verifying the chain
        doesn&apos;t just flag event #14. It flags every event from #14 through #4471, because
        each one&apos;s stored hash depends on the one before it. There&apos;s no way to make a
        silent, localized edit. Tampering anywhere breaks the chain visibly, from that point
        forward.
      </p>

      <h2 style={proseStyles.h2}>Why &quot;we didn&apos;t edit it&quot; isn&apos;t enough</h2>
      <p style={proseStyles.p}>
        For an internal debugging trace, trusting your own team not to have tampered with a log
        is reasonable. For a compliance audit, it isn&apos;t, the entire point of an audit is
        that a third party doesn&apos;t have to take your word for it. Hash-chaining closes one
        specific gap: nobody, including someone with ordinary write access to the log, can edit a
        row without every event after it failing verification. It doesn&apos;t by itself remove
        trust in whoever hosts the database, that requires a separate, independent witness (for
        example, periodically anchoring the chain&apos;s state somewhere the vendor doesn&apos;t
        control) so a third party can check integrity without taking the vendor&apos;s word for
        it either.
      </p>

      <h2 style={proseStyles.h2}>What to check in your own logging</h2>
      <ul style={{ paddingLeft: "1.2rem", marginBottom: "1.1rem" }}>
        <li style={proseStyles.li}>Can any single row be edited or deleted without affecting anything else in the log?</li>
        <li style={proseStyles.li}>If so, is there any independent way to detect that it happened?</li>
        <li style={proseStyles.li}>Would your current setup survive an auditor asking &quot;how do I know this log is complete and unaltered?&quot;</li>
        <li style={proseStyles.li}>Is the answer verifiable by someone who doesn&apos;t have to trust the vendor&apos;s own database, or only by the vendor?</li>
      </ul>
      <p style={proseStyles.p}>
        If the answer to the last question is &quot;you&apos;d have to trust us,&quot; hash-chaining
        narrows that gap, tampering becomes visible instead of invisible, but doesn&apos;t close
        it fully until the log is also anchored outside the vendor&apos;s own infrastructure.
      </p>
    </ArticleLayout>
  );
}
