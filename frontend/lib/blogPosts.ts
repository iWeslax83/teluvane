// frontend/lib/blogPosts.ts
export type BlogPost = {
  slug: string;
  title: string;
  description: string;
  date: string; // ISO date
};

export const blogPosts: BlogPost[] = [
  {
    slug: "eu-ai-act-article-50-2026",
    title: "EU AI Act Article 50: what changes for AI agents in 2026",
    description:
      "Article 50 transparency obligations take effect in 2026. Here's what that actually requires from a team running AI agents in production, and what's still delayed to 2027.",
    date: "2026-08-23",
  },
  {
    slug: "tamper-evident-agent-logs",
    title: "Why AI agent logs need tamper-evidence, not just timestamps",
    description:
      "A timestamped log tells you what an agent did. It doesn't tell you the log wasn't edited afterward. Hash-chaining closes that gap, here's how and why it matters for audits.",
    date: "2026-08-23",
  },
  {
    slug: "iso-42001-nist-ai-rmf-soc2",
    title: "ISO 42001, NIST AI RMF, SOC 2: which framework actually applies to you",
    description:
      "Three frameworks, three different jobs. A plain-language guide to what each one certifies, who asks for it, and how AI agent audit logs fit into each.",
    date: "2026-08-23",
  },
];
