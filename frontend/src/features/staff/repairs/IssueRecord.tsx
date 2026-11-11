import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { KeyValueCard, StatusPill } from "../../../components/ui";
import { CHANNEL_LABELS, type Channel } from "../technicians/techniciansApi";
import { useCrossLink } from "../crossLinks/staffHref";
import type { IssueDetail } from "./repairsApi";

const when = (iso: string | null) => iso ? new Date(iso).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" }) : "";
const EVENT_LABELS: Record<string, string> = {
  reported: t`Reported`, triaged: t`Triaged`, rejected: t`Rejected`, assigned: t`Assigned`, unassigned: t`Assignee removed`,
  dispatched: t`Sent to technician`, visit: t`Visit`, started: t`Work started`, remark: t`Remark`, parts_used: t`Part used`,
  parts_needed: t`Part needed`, quote: t`Quote`, quote_approved: t`Quote approved`, quote_declined: t`Quote declined`,
  payout: t`Payout recorded`, fixed: t`Fixed`, closed: t`Closed`, service_state: t`Service state`,
};

/** The issue's record: the report, photos, who works it, the quote, parts, sends and the full history. */
export function IssueRecord({ issue }: { issue: IssueDetail }) {
  // A18: the work order and the machine open in Machines when this person can open that tab.
  const link = useCrossLink();
  const orderHref = issue.work_order_id ? link("machines", { view: "work-orders", work_order: issue.work_order_id }) : undefined;
  const machineHref = issue.subject_type === "machine" ? link("machines", { machine: issue.subject_id }) : undefined;
  return <>
    <section className="grid gap-2" aria-label={t`Report`}>
      <p className="whitespace-pre-wrap break-words">{issue.description || t`No details given.`}</p>
      {issue.viewer_role === "manager" && issue.reporter_email
        ? <p className="text-sm text-muted">{t`Reporter's email: ${issue.reporter_email}`}</p> : null}
    </section>
    {issue.photos.length ? <section aria-label={t`Photos`} className="flex flex-wrap gap-3">
      {issue.photos.map(photo => photo.url ? <a key={photo.id} href={photo.url} target="_blank" rel="noreferrer">
        <img src={photo.url} alt={photo.stage === "reported" ? t`Photo taken with the report` : photo.stage === "fixed" ? t`Photo taken with the fix` : t`Photo taken during the work`}
          loading="lazy" className="h-24 w-24 rounded-xl border border-line object-cover" /></a> : null)}
    </section> : null}
    <KeyValueCard title={t`Record`} items={[
      { label: t`Working on it`, value: issue.assignees.map(row => row.name).join(", ") || "Nobody yet" },
      ...(issue.quote_amount ? [{ label: t`Quote`, value: `${issue.quote_amount} ${issue.quote_currency.toUpperCase()}${issue.quote_note ? ` · ${issue.quote_note}` : ""}` }] : []),
      ...(issue.payout_entry_id ? [{ label: t`Payout`, value: `Ledger entry #${issue.payout_entry_id}` }] : []),
      ...(issue.resolution ? [{ label: issue.state === "rejected" ? t`Reason` : t`Fix`, value: issue.resolution }] : []),
      ...(machineHref ? [{ label: t`Machine`, value: <a className="text-accent-ink underline underline-offset-4" href={machineHref}>{issue.subject_label}</a> }] : []),
      ...(issue.work_order_id ? [{ label: t`Work order`, value: orderHref
        ? <a className="text-accent-ink underline underline-offset-4" href={orderHref}>{t`Open work order ${issue.work_order_id}`}</a> : t`Work order ${issue.work_order_id}` }] : []),
      { label: t`Reported`, value: when(issue.created_at) },
      ...(issue.fixed_at ? [{ label: t`Fixed`, value: issue.reporter_notified_at ? t`${when(issue.fixed_at)} · reporter told` : when(issue.fixed_at) }] : []),
    ]} />
    {issue.parts.length ? <section aria-label={t`Parts`} className="grid gap-1">
      <h2 className="title-section">{t`Parts`}</h2>
      {issue.parts.map(part => <p key={part.id} className="text-sm">{part.quantity} × {part.name}
        <span className="text-muted"> · {part.kind === "used" ? t`used from stock` : part.to_buy_item_id ? t`on To-Buy` : t`needed`}</span></p>)}
    </section> : null}
    {issue.dispatches.length ? <section aria-label={t`Sent to technicians`} className="grid gap-2">
      <h2 className="title-section">{t`Sent to technicians`}</h2>
      {issue.dispatches.map(row => <p key={row.id} className="flex flex-wrap items-center gap-2 text-sm">
        <span>{row.contact_name} · {CHANNEL_LABELS()[row.channel as Channel] ?? row.channel} · {when(row.sent_at)}</span>
        <StatusPill tone={row.status === "delivered" ? "success" : "danger"} label={row.status === "delivered" ? t`Sent` : (row.failure_code ? t`Failed: ${row.failure_code.replace(/_/g, " ")}` : t`Failed`)} />
      </p>)}
    </section> : null}
    <section aria-label={t`History`} className="grid gap-2">
      <h2 className="title-section">{t`History`}</h2>
      <ol className="grid gap-2">
        {issue.events.map(event => <li key={event.id} className="rounded-xl border border-line bg-panel p-3 text-sm">
          <p className="font-semibold">{EVENT_LABELS[event.kind] ?? event.kind}
            <span className="font-normal text-muted"> · {[event.actor_name, event.contact_name].filter(Boolean).join(" for ")} · <time dateTime={event.created_at}>{when(event.created_at)}</time></span></p>
          {event.occurred_on ? <p className="text-muted">{t`Visit on ${new Date(`${event.occurred_on}T00:00:00`).toLocaleDateString(formatLocale())}`}</p> : null}
          {event.amount ? <p>{event.amount} {event.currency.toUpperCase()}</p> : null}
          {event.note ? <p className="whitespace-pre-wrap break-words">{event.note}</p> : null}
        </li>)}
      </ol>
    </section>
  </>;
}
