import { formatLocale } from "../../../../lib/format";
import { t } from "@lingui/core/macro";
import { ArrowDown, ArrowUp, GripVertical } from "lucide-react";

import { OverflowMenu, StatusBadge, StatusPill } from "../../../../components/ui";
import type { MachineServiceRequest } from "../../../../generated/api";
import type { DialogAction } from "./jobActionBody";
import { AT_RISK_LABELS, CHANGE_CODES } from "./jobLabels";
import { machineStatusLabel } from "./machineStatusLabel";
import type { CardDrag } from "./boardDrag";
import type { BoardAction, StaffJob } from "./machineJobsApi";
import { ServiceEtaLine } from "./ServiceEtaLine";
import { useStaffChargesOn } from "../../useStaffChargesOn";
import { ChargeSettle } from "../../areaPayments/ChargeSettle";

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
/** Settling a job charge changes the board, the job lists and the pickup desk. */
const JOB_PAYMENT_KEYS = [["machine-job-board"], ["machine-service-requests"], ["machine-service-handover"]] as const;
const changeLabel = (code?: string) => CHANGE_CODES.find(([value]) => value === code)?.[1];

/** One job on the queue board: what it is, why it needs attention, and the next step as the primary button. */
export function JobBoardCard({ job, overdue, noShow, pending, move, select, drag, onDialog, onDirect, onUncollected, onFiles }: Props) {
  const quoteTotal = job.quote_snapshot?.total ? `${job.quote_snapshot.total} ${(job.quote_snapshot.currency ?? "").toUpperCase()}`.trim() : "";
  const paid = PAID.has(job.payment?.status ?? "");
  const neededBy = job.needed_by ? new Date(`${job.needed_by}T00:00:00`).toLocaleDateString(formatLocale()) : "";
  const meta = [job.requester_name || t`Member`, job.copies && job.copies > 1 ? t`${job.copies} copies` : "",
    job.estimated_minutes ? t`${job.estimated_minutes} min` : job.member_estimate_minutes ? t`Member estimate ${job.member_estimate_minutes} min` : "",
    neededBy ? t`Needed by ${neededBy}` : "",
    job.own_material ? t`Own material` : ""].filter(Boolean).join(" · ");
  const action = primaryAction(job, paid);
  const files = [{ label: job.files?.length ? t`Files (${job.files.length})` : t`Add a file`, onClick: () => onFiles(job) }];
  // #184 G3: with machine charges off there is no quote to send (the server refuses one).
  const chargesOn = useStaffChargesOn("machines");
  const overflow = [...files, ...overflowActions(job, overdue, chargesOn, { onDialog, onDirect, onUncollected, onFiles })];
  const { dragging = false, over = false, ...dragHandlers } = drag ?? ({} as Partial<CardDrag>);
  const frame = over ? "border-accent outline-2 outline-dashed outline-focus" : "border-line";
  return <li className={`grid gap-2 rounded-2xl border bg-panel p-3 ${frame}${dragging ? " opacity-60" : ""}${drag ? " cursor-grab" : ""}`}
    {...dragHandlers}>
    <div className="flex min-w-0 items-start gap-2">
      {drag ? <GripVertical aria-hidden="true" size={18} className="mt-1 shrink-0 text-muted" /> : null}
      {select ? <label className="-my-2 -ml-2 grid size-11 shrink-0 cursor-pointer place-items-center">
        <input type="checkbox" className="size-5" aria-label={t`Select ${job.title} for a batch`} checked={select.checked}
          onChange={event => select.onChange(event.target.checked)} /></label> : null}
      <div className="min-w-0 flex-1">
        <h4 className="title-section break-words">{job.title}</h4>
        <p className="text-sm text-muted [overflow-wrap:anywhere]">{meta}</p>
      </div>
      <StatusBadge status={job.status} label={machineStatusLabel(job.status)} />
    </div>
    <div className="flex flex-wrap gap-1.5">
      {job.urgent ? <StatusPill tone="danger" label={job.urgent_reason ? t`Urgent: ${job.urgent_reason}` : t`Urgent`} /> : null}
      {job.at_risk_reasons?.length ? <StatusPill tone="warn" label={AT_RISK_LABELS[job.at_risk_reasons[0]] ?? t`At risk`} /> : null}
      {overdue ? <StatusPill tone="danger" label={t`Waiting over 14 days`} /> : null}
      {noShow ? <StatusPill tone="warn" label={t`Member has missed pickups before`} /> : null}
      {job.status === "changes_requested" && job.changes_code ? <StatusPill tone="warn" label={changeLabel(job.changes_code) ?? t`Changes asked`} /> : null}
      {job.status === "quoted" ? <StatusPill tone={job.quote_approved_at ? "success" : "neutral"} label={job.quote_approved_at ? (quoteTotal ? t`Approved ${quoteTotal}` : t`Approved`) : (quoteTotal ? t`Quote ${quoteTotal}` : t`Quote`)} /> : null}
      {job.status === "quoted" && job.prepay && job.quote_approved_at && !paid ? <StatusPill tone="warn" label={t`Waiting for payment`} /> : null}
      {job.batch_id ? <StatusPill tone="neutral" label={t`Batch ${job.batch_id}`} /> : null}
      {job.pickup_location && job.status === "completed" ? <StatusPill tone="neutral" label={t`At ${job.pickup_location}`} /> : null}
    </div>
    <ServiceEtaLine request={job as unknown as MachineServiceRequest} />
    {/* Decision 242(a): record the cash or waive the job charge right here (M3). */}
    <ChargeSettle charge={job.payment} invalidateKeys={JOB_PAYMENT_KEYS} />
    <div className="flex flex-wrap items-center gap-2">
      {action ? <button type="button" className={action.className} disabled={pending}
        onClick={() => action.direct ? onDirect(job, action.direct) : onDialog(job, action.dialog!)}>{action.label}</button> : null}
      {move ? <>
        <button type="button" className="desk-button-ghost min-h-11 min-w-11" aria-label={t`Move ${job.title} up`} disabled={pending || move.up === null}
          onClick={() => move.up !== null && onDirect(job, "reorder", { position: move.up })}><ArrowUp aria-hidden="true" size={16} /></button>
        <button type="button" className="desk-button-ghost min-h-11 min-w-11" aria-label={t`Move ${job.title} down`} disabled={pending || move.down === null}
          onClick={() => move.down !== null && onDirect(job, "reorder", { position: move.down })}><ArrowDown aria-hidden="true" size={16} /></button>
      </> : null}
      {overflow.length ? <OverflowMenu actions={overflow} /> : null}
    </div>
  </li>;
}

type Primary = { label: string; className: string; dialog?: DialogAction; direct?: BoardAction };
function primaryAction(job: StaffJob, paid: boolean): Primary | null {
  if (job.status === "pending") return { label: t`Accept`, className: "desk-button-success", dialog: "accept" };
  if (job.status === "accepted") return { label: t`Start`, className: "desk-button-primary", dialog: "start" };
  if (job.status === "in_progress") return { label: t`Complete`, className: "desk-button-success", dialog: "complete" };
  if (job.status === "completed") return { label: t`Collect`, className: "desk-button-success", dialog: "collect" };
  if (job.status === "quoted" && job.prepay && job.quote_approved_at && paid) return { label: t`Queue now`, className: "desk-button-primary", direct: "queue-now" };
  return null;
}

function overflowActions(job: StaffJob, overdue: boolean | undefined, chargesOn: boolean, { onDialog, onDirect, onUncollected }: CardHandlers) {
  const dialog = (label: string, action: DialogAction, tone?: "danger") => ({ label, tone, onClick: () => onDialog(job, action) });
  const reject = dialog(t`Reject`, "reject", "danger");
  const urgent = job.urgent ? { label: t`Remove urgent`, onClick: () => onDirect(job, "urgent", { urgent: false, reason: "" }) } : dialog(t`Mark urgent`, "urgent");
  switch (job.status) {
    case "pending": return [...(chargesOn ? [dialog(t`Send quote`, "quote")] : []), dialog(t`Ask for changes`, "request-changes"), urgent, dialog(t`Assign to a machine`, "assign"), reject];
    case "accepted": return [urgent, dialog(t`Assign to a machine`, "assign")];
    case "quoted": return job.quote_approved_at ? [] : [...(chargesOn ? [dialog(t`Send a new quote`, "quote")] : []), reject];
    case "changes_requested": return [reject];
    case "in_progress": return [dialog(t`Mark failed`, "fail", "danger")];
    case "completed": return overdue ? [{ label: t`Mark not collected`, tone: "danger" as const, onClick: () => onUncollected(job) }] : [];
    default: return [];
  }
}
