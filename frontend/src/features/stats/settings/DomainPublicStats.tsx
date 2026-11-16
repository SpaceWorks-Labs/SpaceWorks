import { t } from "@lingui/core/macro";
import { useState } from "react";
import { PublicStatsSettingsPanel } from "./PublicStatsSettingsPanel";

/** Fetch manager-specific choices only when their inline editor is opened. */
export function DomainPublicStats({ makerspaceId, area }: { makerspaceId: number; area: string }) {
  const [open, setOpen] = useState(false);
  return <details className="mb-4 rounded-xl border border-line bg-panel" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="min-h-11 cursor-pointer px-4 py-3 font-semibold">{t`Public stats visibility`}</summary>
    {open ? <div className="p-3"><PublicStatsSettingsPanel makerspaceId={makerspaceId} slug="" area={area} /></div> : null}
  </details>;
}
