import { KeyValueCard, StatusPill } from "../../../components/ui";
import { CHANNEL_LABELS, type Channel } from "../technicians/techniciansApi";
import type { IssueDetail } from "./repairsApi";

const when = (iso: string | null) => iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";
const EVENT_LABELS: Record<string, string> = {
  reported: "Reported", triaged: "Triaged", rejected: "Rejected", assigned: "Assigned", unassigned: "Assignee removed",
  dispatched: "Sent to technician", visit: "Visit", started: "Work started", remark: "Remark", parts_used: "Part used",
  parts_needed: "Part needed", quote: "Quote", quote_approved: "Quote approved", quote_declined: "Quote declined",
  payout: "Payout recorded", fixed: "Fixed", closed: "Closed", service_state: "Service state",
};

/** The issue's record: the report, photos, who works it, the quote, parts, sends and the full history. */
export function IssueRecord({ issue }: { issue: IssueDetail }) {
  return <>
    <section className="grid gap-2" aria-label="Report">
      <p className="whitespace-pre-wrap break-words">{issue.description || "No details given."}</p>
      {issue.viewer_role === "manager" && issue.reporter_email
        ? <p className="text-sm text-muted">Reporter's email: {issue.reporter_email}</p> : null}
    </section>
    {issue.photos.length ? <section aria-label="Photos" className="flex flex-wrap gap-3">
      {issue.photos.map(photo => photo.url ? <a key={photo.id} href={photo.url} target="_blank" rel="noreferrer">
        <img src={photo.url} alt={`Photo taken ${photo.stage === "reported" ? "with the report" : photo.stage === "fixed" ? "with the fix" : "during the work"}`}
          loading="lazy" className="h-24 w-24 rounded-xl border border-line object-cover" /></a> : null)}
    </section> : null}
    <KeyValueCard title="Record" items={[
      { label: "Working on it", value: issue.assignees.map(row => row.name).join(", ") || "Nobody yet" },
      ...(issue.quote_amount ? [{ label: "Quote", value: `${issue.quote_amount} ${issue.quote_currency.toUpperCase()}${issue.quote_note ? ` · ${issue.quote_note}` : ""}` }] : []),
      ...(issue.payout_entry_id ? [{ label: "Payout", value: `Ledger entry #${issue.payout_entry_id}` }] : []),
      ...(issue.resolution ? [{ label: issue.state === "rejected" ? "Reason" : "Fix", value: issue.resolution }] : []),
      ...(issue.work_order_id ? [{ label: "Work order", value: `#${issue.work_order_id}` }] : []),
      { label: "Reported", value: when(issue.created_at) },
      ...(issue.fixed_at ? [{ label: "Fixed", value: `${when(issue.fixed_at)}${issue.reporter_notified_at ? " · reporter told" : ""}` }] : []),
    ]} />
    {issue.parts.length ? <section aria-label="Parts" className="grid gap-1">
      <h2 className="title-section">Parts</h2>
      {issue.parts.map(part => <p key={part.id} className="text-sm">{part.quantity} × {part.name}
        <span className="text-muted"> · {part.kind === "used" ? "used from stock" : part.to_buy_item_id ? "on To-Buy" : "needed"}</span></p>)}
    </section> : null}
    {issue.dispatches.length ? <section aria-label="Sent to technicians" className="grid gap-2">
      <h2 className="title-section">Sent to technicians</h2>
      {issue.dispatches.map(row => <p key={row.id} className="flex flex-wrap items-center gap-2 text-sm">
        <span>{row.contact_name} · {CHANNEL_LABELS[row.channel as Channel] ?? row.channel} · {when(row.sent_at)}</span>
        <StatusPill tone={row.status === "delivered" ? "success" : "danger"} label={row.status === "delivered" ? "Sent" : `Failed${row.failure_code ? `: ${row.failure_code.replace(/_/g, " ")}` : ""}`} />
      </p>)}
    </section> : null}
    <section aria-label="History" className="grid gap-2">
      <h2 className="title-section">History</h2>
      <ol className="grid gap-2">
        {issue.events.map(event => <li key={event.id} className="rounded-xl border border-line bg-panel p-3 text-sm">
          <p className="font-semibold">{EVENT_LABELS[event.kind] ?? event.kind}
            <span className="font-normal text-muted"> · {[event.actor_name, event.contact_name].filter(Boolean).join(" for ")} · <time dateTime={event.created_at}>{when(event.created_at)}</time></span></p>
          {event.occurred_on ? <p className="text-muted">Visit on {new Date(`${event.occurred_on}T00:00:00`).toLocaleDateString()}</p> : null}
          {event.amount ? <p>{event.amount} {event.currency.toUpperCase()}</p> : null}
          {event.note ? <p className="whitespace-pre-wrap break-words">{event.note}</p> : null}
        </li>)}
      </ol>
    </section>
  </>;
}
