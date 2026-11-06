// Preflight: the checks list. Choosing an issue with a layer selects that layer (switching
// side if needed) so the inspector shows what to change.
import { CircleAlert, Info, ShieldCheck, TriangleAlert } from "lucide-react";

import type { SideName } from "./cardTypes";
import type { Issue, Severity } from "./preflight";

const LOOK: Record<Severity, { icon: typeof Info; label: string; className: string }> = {
  error: { icon: CircleAlert, label: "Must fix", className: "text-danger" },
  warn: { icon: TriangleAlert, label: "Check", className: "text-warn-ink" },
  info: { icon: Info, label: "Note", className: "text-muted" },
};

export function PreflightPanel({ issues, onPick }: { issues: Issue[]; onPick: (side: SideName, layerId: string | null) => void }) {
  const errors = issues.filter((issue) => issue.severity === "error").length;
  const warnings = issues.filter((issue) => issue.severity === "warn").length;
  return <div className="grid gap-3">
    <div className="grid gap-1">
      <h3 className="text-sm font-semibold text-ink">Checks before printing</h3>
      <p role="status" className="text-sm text-muted">
        {errors || warnings ? [errors ? `${errors} to fix before publishing` : "", warnings ? `${warnings} to check` : ""]
          .filter(Boolean).join(", ") + "." : "Nothing to fix. This design is ready to print."}</p>
    </div>
    {!issues.length ? <p className="flex items-center gap-2 text-sm text-success-ink">
      <ShieldCheck size={18} aria-hidden="true" /> All checks passed</p> : null}
    <ul className="grid gap-1" aria-label="Issues">
      {issues.map((issue) => {
        const look = LOOK[issue.severity];
        const Icon = look.icon;
        const body = <>
          <Icon size={16} aria-hidden="true" className={`mt-0.5 shrink-0 ${look.className}`} />
          <span className="min-w-0"><span className="sr-only">{look.label}: </span>{issue.message}
            <span className="block text-xs text-muted">{issue.side === "front" ? "Front" : "Back"}</span></span>
        </>;
        return <li key={issue.id}>
          <button type="button" onClick={() => onPick(issue.side, issue.layerId)}
            aria-label={`${look.label}: ${issue.message} ${issue.layerId ? "Select the layer" : `Show the ${issue.side}`}.`}
            className="flex min-h-11 w-full items-start gap-2 rounded-control px-2 py-2 text-left text-sm text-ink hover:bg-hover focus-visible:outline-2 focus-visible:outline-focus">
            {body}</button>
        </li>;
      })}
    </ul>
  </div>;
}
