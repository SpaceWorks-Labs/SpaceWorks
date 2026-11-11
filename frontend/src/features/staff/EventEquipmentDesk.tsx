import { plural, t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useContext, useState, type ContextType } from "react";

import { StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { capabilityOn } from "../../lib/features";
import { formatLocale } from "../../lib/format";
import { HandoverWizard } from "./handover/HandoverWizard";
import { LoanRepairsPanel } from "./loanRepairs/LoanRepairsPanel";
import type { HardwareRequest } from "./panels/Queues";
import type { Makerspace } from "./panels/shared";
import { StaffListContext } from "./StaffListContext";
import { EventReturnWindowField } from "./eventEquipment/EventReturnWindowField";

type Row = HardwareRequest & { makerspace_id?: number };
type EquipmentWarning = { product_id: number; product_name: string; code: "units_under_repair" | "reserved_units_unavailable" | "insufficient_stock"; count: number };
type Desk = {
  summary: { awaiting_review: number; equipment_warnings?: EquipmentWarning[]; ready_to_issue: number; out: number; overdue: number; outstanding_units: number; closed_with_issue: number; event_ends_at: string | null; equipment_return_hours?: number | null };
  ready: Row[]; out: Row[]; closed: Row[];
};

function warningText({ product_name: name, code, count }: EquipmentWarning) {
  if (code === "units_under_repair") return t`${name}: ${count} under repair or waiting to be fixed.`;
  if (code === "reserved_units_unavailable") return t`${name}: ${count} reserved units are not on the shelf. An accepted loan may not be issuable in full.`;
  return t`${name}: requests awaiting review ask for ${count}, more than is available now.`;
}

const when = (value: string | null) => value ? new Date(value).toLocaleString(formatLocale()) : t`No due time`;
const holder = (row: Row) => row.requester_display || row.requester_username;
const outstanding = (row: Row) => row.items.reduce((sum, item) => sum + Math.max(0, item.issued_quantity - item.returned_quantity - item.damaged_quantity - item.missing_quantity), 0);
const items = (row: Row, key: "accepted_quantity" | "issued_quantity") => row.items.map(item => `${item.product_name} × ${item[key]}`).join(", ");

/** Event-day desk: this event's linked loans, issued and returned through the normal evidence wizard. */
export function EventEquipmentDesk({ makerspaceId, eventId, canEditWindow = false }: { makerspaceId: number; eventId: number;
  /** Event edit_details: set the per-event return window here (decision 221b). */
  canEditWindow?: boolean }) {
  const { actorId, actions, isSuperadmin, makerspace } = useContext(StaffListContext);
  const modules = makerspace?.enabled_modules ?? [];
  if (!actorId || makerspace?.id !== makerspaceId || !modules.includes("events") || !modules.includes("request_workflow")
      || !capabilityOn(makerspace, "loans.enabled") || !(isSuperadmin || actions?.includes("issue_request"))) return null;
  return <DeskBody key={`${actorId}:${makerspaceId}:${eventId}`} makerspace={makerspace} eventId={eventId} canScanCards={Boolean(isSuperadmin || actions?.includes("scan_member_cards"))} canEditWindow={canEditWindow} />;
}

function DeskBody({ makerspace, eventId, canScanCards, canEditWindow }: { makerspace: NonNullable<ContextType<typeof StaffListContext>["makerspace"]>; eventId: number; canScanCards: boolean; canEditWindow: boolean }) {
  const [guided, setGuided] = useState<{ row: Row; mode: "issue" | "return" } | null>(null);
  const desk = useQuery({
    queryKey: ["event-equipment-desk", makerspace.id, eventId], retry: false,
    queryFn: ({ signal }) => staffRequest<Desk>(`/admin/makerspace/${makerspace.id}/events/${eventId}/equipment-desk`, { signal }),
  });
  if (desk.isPending) return <p role="status">{t`Loading event equipment…`}</p>;
  // A 404 means no inventory or event authority here; the desk simply is not offered.
  if (desk.isError) return null;
  const { summary, ready, out, closed } = desk.data;
  const damaged = closed.filter(row => row.items.some(item => item.damaged_quantity + item.missing_quantity > 0));
  const ended = summary.event_ends_at !== null && Date.parse(summary.event_ends_at) < Date.now();
  const idle = !summary.awaiting_review && !ready.length && !out.length && !damaged.length;
  if (idle && !canEditWindow) return null;
  const returnHours = summary.equipment_return_hours ?? null;
  return <section className="grid gap-3" aria-labelledby={`event-equipment-${eventId}`} data-replay-block>
    <h3 id={`event-equipment-${eventId}`} className="title-section">{t`Event equipment`}</h3>
    <div className="flex flex-wrap gap-2">
      {summary.awaiting_review ? <StatusPill tone="info" label={t`${summary.awaiting_review} awaiting review`} /> : null}
      <StatusPill tone="neutral" label={t`${summary.ready_to_issue} ready to issue`} />
      <StatusPill tone={summary.out ? "warn" : "success"} label={plural(summary.outstanding_units, { one: "# unit out", other: "# units out" })} />
      {summary.overdue ? <StatusPill tone="danger" label={t`${summary.overdue} overdue`} /> : null}
    </div>
    {summary.equipment_warnings?.length ? <ul className="grid gap-1 text-sm" aria-label={t`Equipment warnings`}>
      {summary.equipment_warnings.map(row => <li key={`${row.product_id}:${row.code}`} role="status" className="flex flex-wrap items-center gap-2">
        <StatusPill tone="warn" label={t`Warning`} /><span>{warningText(row)}</span></li>)}</ul> : null}
    {canEditWindow ? <EventReturnWindowField makerspaceId={makerspace.id} eventId={eventId} hours={returnHours} />
      : <p className="text-sm text-muted">{returnHours ? t`Items are due ${returnHours} hours after the event ends.` : t`Items are due when the event ends.`}</p>}
    {summary.awaiting_review ? <p className="text-sm text-muted">{t`Requests awaiting review are accepted or rejected in Requests by inventory staff.`}</p> : null}
    {ready.length ? <div className="grid gap-2"><h4 className="font-semibold">{t`Ready to issue`}</h4><ul className="grid gap-2">
      {ready.map(row => <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line p-2">
        <span className="grid [overflow-wrap:anywhere]"><strong>{holder(row)}</strong><span className="text-sm">{items(row, "accepted_quantity")}</span></span>
        <button className="desk-button" type="button" onClick={() => setGuided({ row, mode: "issue" })}>{t`Issue`}<span className="sr-only"> {t`request #${row.id}`}</span></button>
      </li>)}</ul></div> : null}
    {out.length ? <div className="grid gap-2"><h4 className="font-semibold">{ended ? t`Still out after the event` : t`Out with participants`}</h4><ul className="grid gap-2">
      {out.map(row => { const late = row.return_due_at !== null && Date.parse(row.return_due_at) < Date.now();
        return <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line p-2">
          <span className="grid [overflow-wrap:anywhere]"><strong>{holder(row)}</strong>
            <span className="text-sm">{items(row, "issued_quantity")} · {t`${outstanding(row)} outstanding`}</span>
            <span className="text-sm">{t`Due back ${when(row.return_due_at)}`} {late ? <StatusPill tone="danger" label={t`Overdue`} /> : null}</span></span>
          <button className="desk-button" type="button" onClick={() => setGuided({ row, mode: "return" })}>{t`Return`}<span className="sr-only"> {t`request #${row.id}`}</span></button>
        </li>; })}</ul></div> : null}
    {damaged.length ? <div className="grid gap-2"><h4 className="font-semibold">{t`Returned damaged or missing`}</h4>
      {damaged.map(row => <div key={row.id} className="grid gap-1"><span>{holder(row)} · {t`Request #${row.id}`}</span><LoanRepairsPanel loan={{ ...row, makerspace_id: row.makerspace_id ?? makerspace.id }} /></div>)}</div> : null}
    {guided ? <HandoverWizard key={`${guided.row.id}:${guided.mode}`} row={guided.row} mode={guided.mode} makerspace={makerspace as Makerspace} canScanCards={canScanCards}
      onClose={() => { setGuided(null); void desk.refetch(); }} /> : null}
  </section>;
}
