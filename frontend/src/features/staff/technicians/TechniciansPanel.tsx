import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ListLayout } from "../../../components/layouts";
import { ListRow, StatusPill } from "../../../components/ui";
import type { Makerspace } from "../panels/shared";
import { opsQueryState } from "../opsPresentation";
import { TechnicianForm } from "./TechnicianForm";
import { CHANNEL_LABELS, useTechnicians, type Channel, type Technician } from "./techniciansApi";

/**
 * The technician directory (#98): in-house people and outside contractors, what they cover,
 * and which channels they can be reached on. Contractors never sign in; a chat channel works
 * only after their one-time opt-in.
 */
export function TechniciansPanel({ makerspace, canSetCoverage }: { makerspace: Makerspace; canSetCoverage: boolean }) {
  const list = useTechnicians(makerspace.id);
  const [editing, setEditing] = useState<Technician | "new" | null>(null);
  const rows = list.data ?? [];
  return <>
    <ListLayout header={{ title: t`Technicians`, subtitle: t`Who you send repairs to. Email always works; chat needs their opt-in.`,
      primary: { label: t`Add technician`, icon: "Plus", onClick: () => setEditing("new") } }}
      state={opsQueryState(list, "technicians")} isEmpty={!rows.length}
      empty={{ message: t`No technicians yet. Add an in-house Technician or an outside contractor.` }}
      body={{ kind: "rows", rows: rows.map(row => <ListRow key={row.id} title={row.name} onClick={() => setEditing(row)}
        identity={{ kind: "icon", icon: "HardHat", tone: row.kind === "in_house" ? "accent" : "neutral" }}
        meta={[row.kind === "in_house" ? "In-house" : "Contractor", row.coverage.map(item => item.label).join(", ") || "No coverage set"].join(" · ")}
        right={<span className="flex flex-wrap gap-1.5">{(Object.keys(CHANNEL_LABELS()) as Channel[]).filter(channel => row.consent[channel])
          .map(channel => <StatusPill key={channel} tone="success" label={CHANNEL_LABELS()[channel]} />)}
          {row.opt_in_pending ? <StatusPill tone="warn" label={t`Opt-in sent`} /> : null}</span>} />) }} />
    {editing ? <TechnicianForm makerspaceId={makerspace.id} technician={editing === "new" ? null : editing}
      canSetCoverage={canSetCoverage} onClose={() => setEditing(null)} /> : null}
  </>;
}
