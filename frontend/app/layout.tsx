import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import JsonLd from "@/components/JsonLd";
import { siteUrl, SITE_NAME, FOUNDER, ORG_SAME_AS } from "@/lib/site";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: { default: "TELUVANE: AI Agent Accountability", template: "%s" },
  description: "Tamper-evident flight recorder + autonomous compliance tribunal for AI agents.",
  applicationName: SITE_NAME,
  authors: [{ name: FOUNDER.name, url: `${siteUrl}/about` }],
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    locale: "en_US",
  },
  twitter: { card: "summary_large_image" },
};

const organizationLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": `${siteUrl}/#organization`,
      name: SITE_NAME,
      url: siteUrl,
      description:
        "Tamper-evident flight recorder and compliance tribunal for AI agents.",
      email: "hello@teluvane.com",
      address: { "@type": "PostalAddress", addressLocality: "Bursa", addressCountry: "TR" },
      founder: { "@id": `${siteUrl}/about#emir-sakarya` },
      sameAs: ORG_SAME_AS,
    },
    {
      "@type": "WebSite",
      "@id": `${siteUrl}/#website`,
      url: siteUrl,
      name: SITE_NAME,
      inLanguage: "en",
      publisher: { "@id": `${siteUrl}/#organization` },
    },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <JsonLd data={organizationLd} />
        <a href="#main-content" className="skip-link">Skip to content</a>
        {children}
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
