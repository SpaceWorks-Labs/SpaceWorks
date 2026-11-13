import { plural, t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { LogoLoader } from "../../components/LogoLoader";
import { StatusPill } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { decideCost, eventUseKeys, fetchEventUse, type MachineUseRow } from "./api";

const money = (values: Record<string, string>) => Object.entries(values).map(([code, amount]) => `${amount} ${code}`).join(", ") || "-";
const consumed = (items: { label: string; unit: string; quantity: string }[]) => items.map(item => `${item.label || item.unit} ${item.quantity}`).join(", ");

function CostCell({ row, canDecide, busy, onDecide }: {
  row: MachineUseRow; canDecide: boolean; busy: boolean; onDecide: (decision: "approved" | "withdrawn") => void;
}) {
  if (!row.charge) return <span className="text-muted">{t`No charge`}</span>;
  return <div className="grid gap-1">
    <span>{row.charge.amount} {row.charge.currency} · {row.charge.status}</span>
    {row.cost_decision === "approved" ? <StatusPill tone="success" label={t`Approved to charge to the event`} /> : null}
    {canDecide ? <button type="button" className="desk-button min-h-11 w-fit" disabled={busy}
      onClick={() => onDecide(row.cost_decision === "approved" ? "withdrawn" : "approved")}>
      {row.cost_decision === "approved" ? t`Withdraw approval` : t`Approve charging the event`}</button> : null}
  </div>;
}

/**
 * The event page's "Machine use" section (decision 342): sessions, jobs and consumables logged for this event.
 * Approving a cost records the organiser's decision only; the member's own charge stands until staff settle it.
 */
export function EventMachineUsePanel({ makerspaceId, eventId }: { makerspaceId: number; eventId: number }) {
  const client = useQueryClient();
  const key = eventUseKeys.event(makerspaceId, eventId);
  const use = useQuery({ queryKey: key, queryFn: () => fetchEventUse(makerspaceId, eventId), retry: false });
  const decide = useMutation({ mutationFn: (input: { linkId: number; decision: "approved" | "withdrawn" }) =>
    decideCost(makerspaceId, eventId, input.linkId, input.decision), onSuccess: () => client.invalidateQueries({ queryKey: key }) });
  if (use.isPending) return <LogoLoader label={t`Loading…`} size={32} className="min-h-12 py-2" />;
  if (use.isError) {
    const hidden = use.error instanceof StructuredApiError && [403, 404].includes(use.error.status);
    return hidden ? null : <p role="alert">{t`Machine use is unavailable. Try again.`}</p>;
  }
  if (!Array.isArray(use.data?.rows)) return null;
  const { rows, totals, can_decide_costs: canDecide } = use.data;
  return <section className="grid gap-3" aria-labelledby="event-machine-use-title">
    <h3 id="event-machine-use-title" className="title-section">{t`Machine use`}</h3>
    {rows.length === 0 ? <p className="text-sm text-muted">{t`Nothing has been logged for this event yet. Members can pick it when they start a machine session or request a job.`}</p> : <>
      <p className="text-sm">{plural(totals.sessions, { one: "# session", other: "# sessions" })}, {plural(totals.bookings ?? 0, { one: "# booking", other: "# bookings" })}, {plural(totals.requests, { one: "# job", other: "# jobs" })}, {t`${totals.minutes} machine minutes`}
        {totals.consumables.length ? ` · ${consumed(totals.consumables)}` : ""}
        {` · ${t`Charged`} ${money(totals.charged)} · ${t`Approved to the event`} ${money(totals.approved_to_event)}`}</p>
      <ul className="grid gap-3">{rows.map(row => <li key={row.link_id} className="desk-panel grid gap-2 p-3 text-sm">
        <div className="flex flex-wrap justify-between gap-2"><strong className="min-w-0 break-words">{row.title}</strong>
          <span className="text-muted">{row.kind === "session" ? t`Session` : row.kind === "booking" ? t`Booking` : t`Job`} · {row.machine_type}</span></div>
        <div className="text-muted">{row.person || "-"} · {t`${row.minutes} min`}{row.consumables.length ? ` · ${consumed(row.consumables)}` : ""}</div>
        <CostCell row={row} canDecide={canDecide} busy={decide.isPending}
          onDecide={decision => decide.mutate({ linkId: row.link_id, decision })} />
      </li>)}</ul>
      {decide.isError ? <p role="alert" className="text-sm text-danger">{t`Couldn't record that decision. Try again.`}</p> : null}
    </>}
  </section>;
}
