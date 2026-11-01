import { useState } from "react";

import { DetailLayout } from "../../../../../components/layouts";
import { KeyValueCard, Modal, StatusPill } from "../../../../../components/ui";
import type { QueryState } from "../../../../../components/ui/types";
import { WorkOrderAssignee } from "./WorkOrderAssignee";
import {
  OPEN_STATUSES, PRIORITY_LABELS, STATUS_LABELS, priorityTone, statusTone, useMoveWorkOrder, type WorkOrder,
} from "./workOrdersApi";

const date = (iso: string | null) => iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "Not yet";

/** One work order: what it is, who has it, and the next step (start, hold, close or cancel). */
export function WorkOrderDetail({ order, state, onBack }: { order: WorkOrder | undefined; state: QueryState; onBack: () => void }) {
  const move = useMoveWorkOrder();
  const [closing, setClosing] = useState(false);
  const open = order ? OPEN_STATUSES.includes(order.status) : false;
  const primary = !order || !open ? undefined
    : order.status === "in_progress" ? { label: "Close work order", onClick: () => setClosing(true) }
    : { label: order.status === "on_hold" ? "Resume work" : "Start work", pending: move.isPending, onClick: () => move.mutate({ id: order.id, status: "in_progress" }) };
  const overflow = order && open ? [
    ...(order.status !== "on_hold" ? [{ label: "Put on hold", onClick: () => move.mutate({ id: order.id, status: "on_hold" }) }] : []),
    { label: "Cancel work order", tone: "danger" as const, onClick: () => move.mutate({ id: order.id, status: "cancelled" }),
      confirm: { title: "Cancel this work order?", message: "It closes without logging maintenance. A machine it took down goes back to idle.", confirmLabel: "Cancel work order" } },
  ] : undefined;
  return <DetailLayout title={order?.title ?? "Work order"} back={{ label: "All work orders", onClick: onBack }}
    identity={{ kind: "icon", icon: "Wrench", tone: "accent" }} state={order || state.status !== "ready" ? state : { status: "error", error: "This work order is not in your scope any more." }}
    status={order ? <><StatusPill tone={statusTone(order.status)} label={STATUS_LABELS[order.status]} />
      <StatusPill tone={priorityTone(order.priority)} label={`${PRIORITY_LABELS[order.priority]} priority`} /></> : undefined}
    meta={order ? [order.subject_label, order.due_on ? `Due ${new Date(`${order.due_on}T00:00:00`).toLocaleDateString()}` : "No due date"] : undefined}
    actions={{ primary, overflow }}
    main={order ? <div className="grid gap-6">
      {move.error ? <p role="alert" className="text-sm text-danger">{move.error.message}</p> : null}
      {order.description ? <p className="whitespace-pre-wrap break-words">{order.description}</p> : <p className="text-sm text-muted">No details given.</p>}
      <WorkOrderAssignee order={order} disabled={!open} />
      <KeyValueCard title="Record" items={[
        { label: "Takes the machine down", value: order.takes_machine_down ? "Yes, while in progress" : "No" },
        { label: "Opened", value: date(order.created_at) }, { label: "Started", value: date(order.started_at) },
        { label: "Closed", value: date(order.closed_at) },
        ...(order.resolution ? [{ label: "Resolution", value: order.resolution }] : []),
        ...(order.log_id ? [{ label: "Maintenance log", value: `Logged as entry #${order.log_id}` }] : []),
      ]} />
      {closing ? <CloseDialog order={order} onClose={() => setClosing(false)} /> : null}
    </div> : null} />;
}

function CloseDialog({ order, onClose }: { order: WorkOrder; onClose: () => void }) {
  const move = useMoveWorkOrder();
  const [resolution, setResolution] = useState("");
  const [cost, setCost] = useState("");
  const [parts, setParts] = useState("");
  return <Modal open title="Close work order" onClose={onClose}>
    <form className="grid gap-3" onSubmit={event => { event.preventDefault();
      move.mutate({ id: order.id, status: "done", resolution: resolution.trim(), cost: cost.trim() || null, parts_note: parts.trim() }, { onSuccess: onClose }); }}>
      <label className="eyebrow grid gap-1">What was done<textarea className="desk-input min-h-24" value={resolution} onChange={event => setResolution(event.target.value)} autoFocus /></label>
      <label className="eyebrow grid gap-1">Cost (optional)<input className="desk-input" type="number" min="0" step="0.01" value={cost} onChange={event => setCost(event.target.value)} /></label>
      <label className="eyebrow grid gap-1">Parts and notes (optional)<textarea className="desk-input min-h-20" value={parts} onChange={event => setParts(event.target.value)} /></label>
      <p className="text-sm text-muted">Closing logs this as maintenance on the machine{order.takes_machine_down ? " and returns it to idle" : ""}.</p>
      {move.error ? <p role="alert" className="text-sm text-danger">{move.error.message}</p> : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
        <button type="button" className="desk-button-ghost" onClick={onClose}>Cancel</button>
        <button type="submit" className="desk-button-success" disabled={move.isPending}>{move.isPending ? "Closing…" : "Close work order"}</button>
      </div>
    </form>
  </Modal>;
}
