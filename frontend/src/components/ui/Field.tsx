import { cloneElement, Fragment, isValidElement, useId, type ReactNode } from "react";
export type FieldProps = { label: string; hint?: string; error?: string; className?: string; children: ReactNode };
export function Field({ label, hint, error, className = "", children }: FieldProps) {
  const id = useId();
  const hintId = id + "-hint";
  const errorId = id + "-error";
  const control = isValidElement<{ "aria-invalid"?: boolean; "aria-describedby"?: string; "aria-labelledby"?: string; "aria-label"?: string }>(children) && children.type !== Fragment
    ? cloneElement(children, {
      "aria-labelledby": children.props["aria-labelledby"] ?? (children.props["aria-label"] ? undefined : id + "-label"),
      ...(error !== undefined ? { "aria-invalid": Boolean(error) } : {}),
      "aria-describedby": [children.props["aria-describedby"], hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined,
    }) : children;
  return <label className={`grid gap-2 ${className}`}>
    <span id={id + "-label"} className="text-sm font-semibold text-ink">{label}</span>{control}
    {hint ? <span id={hintId} className="text-xs text-muted">{hint}</span> : null}
    {error ? <span id={errorId} className="text-xs text-danger">{error}</span> : null}
  </label>;
}
