import type { MetadataRoute } from "next";
import { blogPosts } from "@/lib/blogPosts";
import { siteUrl } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: siteUrl, changeFrequency: "weekly", priority: 1 },
    { url: `${siteUrl}/about`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${siteUrl}/privacy`, changeFrequency: "yearly", priority: 0.2 },
    { url: `${siteUrl}/terms`, changeFrequency: "yearly", priority: 0.2 },
    { url: `${siteUrl}/accessibility`, changeFrequency: "yearly", priority: 0.2 },
    { url: `${siteUrl}/verify`, changeFrequency: "monthly", priority: 0.4 },
    { url: `${siteUrl}/blog`, changeFrequency: "weekly", priority: 0.6 },
    ...blogPosts.map((post) => ({
      url: `${siteUrl}/blog/${post.slug}`,
      lastModified: new Date(post.date),
      changeFrequency: "monthly" as const,
      priority: 0.5,
    })),
  ];
}
