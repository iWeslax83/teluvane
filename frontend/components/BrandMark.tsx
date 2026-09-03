// frontend/components/BrandMark.tsx
// Rendered inside the .brand .mark box (globals.css), transparent/borderless,
// so this fills with currentColor and inherits --accent from .mark.
// Ledger seal: three interlocked plates, one per logged event, notched
// together like the hash chain they represent; the last plate closes with a
// check. The emblem's own outline is the mark, no extra box needed.
export default function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 96 96" fill="none" aria-hidden="true">
      <rect x="10" y="14" width="76" height="18" rx="2" stroke="currentColor" strokeWidth="4" />
      <rect x="10" y="39" width="76" height="18" rx="2" stroke="currentColor" strokeWidth="4" />
      <rect x="10" y="64" width="76" height="18" rx="2" stroke="currentColor" strokeWidth="4" />
      <rect x="41" y="26" width="14" height="10" style={{ fill: "var(--paper)" }} stroke="currentColor" strokeWidth="4" />
      <rect x="41" y="51" width="14" height="10" style={{ fill: "var(--paper)" }} stroke="currentColor" strokeWidth="4" />
      <path d="M38 70 L45 78 L59 62" stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
}
