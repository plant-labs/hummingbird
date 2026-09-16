type Props = {
  label?: string;
  /** Compact inline variant for header status row */
  size?: "sm" | "md";
  className?: string;
};

export default function LoadingIndicator({
  label = "Loading…",
  size = "md",
  className = "",
}: Props) {
  const ring = size === "sm" ? "h-3.5 w-3.5 border" : "h-5 w-5 border-2";
  return (
    <span
      className={`inline-flex items-center gap-2 text-ink/60 ${className}`}
      role="status"
      aria-live="polite"
    >
      <span
        className={`${ring} animate-spin rounded-full border-fern/25 border-t-fern`}
        aria-hidden
      />
      {label ? <span className={size === "sm" ? "text-xs" : "text-sm"}>{label}</span> : null}
    </span>
  );
}
