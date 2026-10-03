// frontend/app/accessibility/page.tsx
import type { Metadata } from "next";
import AccessibilityClient from "./AccessibilityClient";

export const metadata: Metadata = {
  title: "Accessibility: TELUVANE",
  description: "How TELUVANE approaches accessibility, and how to report a problem.",
  alternates: { canonical: "/accessibility" },
};

export default function AccessibilityPage() {
  return <AccessibilityClient />;
}
