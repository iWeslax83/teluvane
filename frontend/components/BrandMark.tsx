// frontend/components/BrandMark.tsx
// Rendered inside the .brand .mark box (globals.css), transparent/borderless.
// The T-bar and V fill with currentColor (inherits --accent from .mark); the
// dot is the second tone and defaults to --ink.
export default function BrandMark({
  size = 28,
  dot = "var(--ink)",
}: {
  size?: number;
  dot?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="92 92 216 216" fill="none" aria-hidden="true">
      <rect x="96" y="102" width="208" height="52" fill="currentColor" />
      <path
        d="M96 178 H304 L200 300 Z M152 178 L200 234 L248 178 Z"
        fill="currentColor"
        fillRule="evenodd"
      />
      <circle cx="200" cy="204" r="13" fill={dot} />
    </svg>
  );
}
