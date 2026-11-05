import { ArrowDown, ArrowUp, GripVertical } from "lucide-react";

import { OverflowMenu, StatusBadge, StatusPill } from "../../../../components/ui";
import type { MachineServiceRequest } from "../../../../generated/api";
import type { DialogAction } from "./jobActionBody";
import { AT_RISK_LABELS, CHANGE_CODES } from "./jobLabels";
import { machineStatusLabel } from "./machineStatusLabel";
import type { CardDrag } from "./boardDrag";
import type { BoardAction, StaffJob } from "./machineJobsApi";
import { ServiceEtaLine } from "./ServiceEtaLine";

export type CardHandlers = {
  onDialog: (job: StaffJob, action: DialogAction) => void;
  onDirect: (job: StaffJob, action: BoardAction, body?: object) => void;
  onUncollected: (job: StaffJob) => void;
  onFiles: (job: StaffJob) => void;
};
type Props = CardHandlers & {
  job: StaffJob; overdue?: boolean; noShow?: boolean; pending?: boolean;
  move?: { up: number | null; down: number | null };
  select?: { checked: boolean; onChange: (checked: boolean) => void };
  drag?: CardDrag;
};

const PAID = new Set(["paid_online", "paid_offline", "waived"]);
const changeLabel = (code?: string) => CHANGE_CODES.find(([value]) => value === code)?.[1];

/** One job on the queue board: what it is, why it needs attention, and the next step as the primary button. */
export function JobBoardCard({ job, overdue, noShow, pending, move, select, drag, onDialog, onDirect, onUncollected, onFiles }: Props) {
  const quoteTotal = job.quote_snapshot?.total ? `${job.quote_snapshot.total} ${(job.quote_snapshot.currency ?? "").toUpperCase()}`.trim() : "";
  const paid = PAID.has(job.payment?.status ?? "");
  const meta = [job.requester_name || "Member", job.copies && job.copies > 1 ? `${job.copies} copies` : "",
    job.estimated_minutes ? `${job.estimated_minutes} min` : job.member_estimate_minutes ? `Member estimate ${job.member_estimate_minutes} min` : "",
    job.needed_by ? `Needed by ${new Date(`${job.needed_by}T00:00:00`).toLocaleDateString()}` : "",
    job.own_material ? "Own material" : ""].filter(Boolean).join(" · ");
  const action = primaryAction(job, paid);
  const files = job.files?.length ? [{ label: `Files (${job.files.length})`, onClick: () => onFiles(job) }] : [];
  const overflow = [...files, ...overflowActions(job, overdue, { onDialog, onDirect, onUncollected, onFiles })];
  const { dragging = false, over = false, ...dragHandlers } = drag ?? ({} as Partial<CardDrag>);
  const frame = over ? "border-accent outline-2 outline-dashed outline-focus" : "border-line";
  return <li className={`grid gap-2 rounded-2xl border bg-panel p-3 ${frame}${dragging ? " opacity-60" : ""}${drag ? " cursor-grab" : ""}`}
    {...dragHandlers}>
    <div className="flex min-w-0 items-start gap-2">
      {drag ? <GripVertical aria-hidden="true" size={18} className="mt-1 shrink-0 text-muted" /> : null}
      {select ? <label className="-my-2 -ml-2 grid size-11 shrink-0 cursor-pointer place-items-center">
        <input type="checkbox" className="size-5" aria-label={`Select ${job.title} for a batch`} checked={select.checked}
          onChange={event => select.onChange(event.target.checked)} /></label> : null}
      <div className="min-w-0 flex-1">
        <h4 className="title-section break-words">{job.title}</h4>
        <p className="text-sm text-muted [overflow-wrap:anywhere]">{meta}</p>
      </div>
      <StatusBadge status={job.status} label={machineStatusLabel(job.status)} />
    </div>
    <div className="flex flex-wrap gap-1.5">
      {job.urgent ? <StatusPill tone="danger" label={job.urgent_reason ? `Urgent: ${job.urgent_reason}` : "Urgent"} /> : null}
      {job.at_risk_reasons?.length ? <StatusPill tone="warn" label={AT_RISK_LABELS[job.at_risk_reasons[0]] ?? "At risk"} /> : null}
      {overdue ? <StatusPill tone="danger" label="Waiting over 14 days" /> : null}
      {noShow ? <StatusPill tone="warn" label="Member has missed pickups before" /> : null}
      {job.status === "changes_requested" && job.changes_code ? <StatusPill tone="warn" label={changeLabel(job.changes_code) ?? "Changes asked"} /> : null}
      {job.status === "quoted" ? <StatusPill tone={job.quote_approved_at ? "success" : "neutral"} label={`${job.quote_approved_at ? "Approved" : "Quote"}${quoteTotal ? ` ${quoteTotal}` : ""}`} /> : null}
      {job.status === "quoted" && job.prepay && job.quote_approved_at && !paid ? <StatusPill tone="warn" label="Waiting for payment" /> : null}
      {job.batch_id ? <StatusPill tone="neutral" label={`Batch ${job.batch_id}`} /> : null}
      {job.pickup_location && job.status === "completed" ? <StatusPill tone="neutral" label={`At ${job.pickup_location}`} /> : null}
    </div>
    <ServiceEtaLine request={job as unknown as MachineServiceRequest} />
    <div className="flex flex-wrap items-center gap-2">
      {action ? <button type="button" className={action.className} disabled={pending}
        onClick={() => action.direct ? onDirect(job, action.direct) : onDialog(job, action.dialog!)}>{action.label}</button> : null}
      {move ? <>
        <button type="button" className="desk-button-ghost min-h-11 min-w-11" aria-label={`Move ${job.title} up`} disabled={pending || move.up === null}
          onClick={() => move.up !== null && onDirect(job, "reorder", { position: move.up })}><ArrowUp aria-hidden="true" size={16} /></button>
        <button type="button" className="desk-button-ghost min-h-11 min-w-11" aria-label={`Move ${job.title} down`} disabled={pending || move.down === null}
          onClick={() => move.down !== null && onDirect(job, "reorder", { position: move.down })}><ArrowDown aria-hidden="true" size={16} /></button>
      </> : null}
      {overflow.length ? <OverflowMenu actions={overflow} /> : null}
    </div>
  </li>;
}

type Primary = { label: string; className: string; dialog?: DialogAction; direct?: BoardAction };
function primaryAction(job: StaffJob, paid: boolean): Primary | null {
  if (job.status === "pending") return { label: "Accept", className: "desk-button-success", dialog: "accept" };
  if (job.status === "accepted") return { label: "Start", className: "desk-button-primary", dialog: "start" };
  if (job.status === "in_progress") return { label: "Complete", className: "desk-button-success", dialog: "complete" };
  if (job.status === "completed") return { label: "Collect", className: "desk-button-success", dialog: "collect" };
  if (job.status === "quoted" && job.prepay && job.quote_approved_at && paid) return { label: "Queue now", className: "desk-button-primary", direct: "queue-now" };
  return null;
}

function overflowActions(job: StaffJob, overdue: boolean | undefined, { onDialog, onDirect, onUncollected }: CardHandlers) {
  const dialog = (label: string, action: DialogAction, tone?: "danger") => ({ label, tone, onClick: () => onDialog(job, action) });
  const reject = dialog("Reject", "reject", "danger");
  const urgent = job.urgent ? { label: "Remove urgent", onClick: () => onDirect(job, "urgent", { urgent: false, reason: "" }) } : dialog("Mark urgent", "urgent");
  switch (job.status) {
    case "pending": return [dialog("Send quote", "quote"), dialog("Ask for changes", "request-changes"), urgent, dialog("Assign to a machine", "assign"), reject];
    case "accepted": return [urgent, dialog("Assign to a machine", "assign")];
    case "quoted": return job.quote_approved_at ? [] : [dialog("Send a new quote", "quote"), reject];
    case "changes_requested": return [reject];
    case "in_progress": return [dialog("Mark failed", "fail", "danger")];
    case "completed": return overdue ? [{ label: "Mark not collected", tone: "danger" as const, onClick: () => onUncollected(job) }] : [];
    default: return [];
  }
}
