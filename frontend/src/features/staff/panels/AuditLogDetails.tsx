import { t } from "@lingui/core/macro";
import { useId, useState } from "react";

/** Projected metadata remains private until the operator opens this disclosure. */
export function AuditLogDetails({ action, meta, redacted }: {
  action: string; meta: Record<string, unknown>; redacted: boolean;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return <div>
    <button type="button" className="desk-button-ghost" aria-expanded={open} aria-controls={open ? id : undefined}
      onClick={() => setOpen(!open)}>{open ? t`Hide details` : t`View details`}</button>
    {open ? <div id={id} className="mt-2 break-words text-xs text-muted">
      <p className="break-all">{action}</p>
      <p>{Object.entries(meta ?? {}).map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`).join(" · ")}
        {redacted ? <span className="ml-1 italic">{t`(some details withheld)`}</span> : null}
      </p>
    </div> : null}
  </div>;
}
