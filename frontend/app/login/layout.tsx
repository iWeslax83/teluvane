import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Log in: TELUVANE",
  description: "Log in to your TELUVANE workspace to audit your AI agents.",
  alternates: { canonical: "/login" },
};

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children;
}
