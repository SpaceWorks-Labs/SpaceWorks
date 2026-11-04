import { useState } from "react";

import { Modal, SegmentedControl } from "../../../components/ui";
import { useServiceState, type IssueDetail, type ServiceStateResult } from "./repairsApi";

/**
 * Take the issue's subject out of service, or back in (#93, C-6b). A room either blocks new
 * bookings (the default) or only warns; bookings already inside the outage are listed for
 * staff to cancel (the member is owed the full amount) or keep, from the Bookings tab.
 */
export function ServiceStateDialog({ issue, makerspaceId, onClose }: { issue: IssueDetail; makerspaceId: number; onClose: () => void }) {
  const change = useServiceState(makerspaceId);
  const [direction, setDirection] = useState("out");
  const [reason, setReason] = useState(issue.title);
  const [back, setBack] = useState("");
  const [mode, setMode] = useState<"block" | "warn">("block");
  const [quantity, setQuantity] = useState("1");
  const [result, setResult] = useState<ServiceStateResult | null>(null);
  const room = issue.subject_type === "bookable_space";
  const counted = issue.subject_type === "inventory_product";
  return <Modal open title="In or out of service" onClose={onClose}>
    {result ? <div className="grid gap-3">
      <p>Done: {issue.subject_label} is now {result.state.replace(/[_:]/g, " ")}.</p>
      {result.affected_bookings.length ? <div className="grid gap-1"><p className="font-semibold">Bookings inside the outage</p>
        {result.affected_bookings.map(row => <p key={row.id} className="text-sm">#{row.id} · {new Date(row.starts_at).toLocaleString()} ({row.status})</p>)}
        <p className="text-sm text-muted">Their bookers were emailed. Cancel or keep each one from the Bookings tab.</p></div> : null}
      <div className="flex justify-end"><button type="button" className="desk-button-primary" onClick={onClose}>Done</button></div>
    </div> : <form className="grid gap-3" onSubmit={event => {
      event.preventDefault();
      change.mutate({ subject_type: issue.subject_type, subject_id: issue.subject_id, in_service: direction === "in", issue_id: issue.id,
        reason: reason.trim(), expected_back_at: back ? new Date(back).toISOString() : null, mode,
        quantity: counted ? Number(quantity) : null }, { onSuccess: setResult });
    }}>
      <SegmentedControl label="Direction" value={direction} onChange={setDirection} fullWidth
        options={[{ value: "out", label: "Out of service" }, { value: "in", label: "Back in service" }]} />
      {direction === "out" ? <>
        <label className="eyebrow grid gap-1">Reason<input className="desk-input" maxLength={300} value={reason} onChange={event => setReason(event.target.value)} /></label>
        <label className="eyebrow grid gap-1">Expected back (optional)<input className="desk-input w-full min-w-0" type="datetime-local" value={back}
          onChange={event => setBack(event.target.value)} /></label>
        {room ? <SegmentedControl label="New bookings" value={mode} onChange={value => setMode(value as "block" | "warn")}
          options={[{ value: "block", label: "Block new bookings" }, { value: "warn", label: "Only warn" }]} /> : null}
      </> : null}
      {counted ? <label className="eyebrow grid gap-1">How many units<input className="desk-input" type="number" min="1" step="1"
        value={quantity} onChange={event => setQuantity(event.target.value)} /></label> : null}
      {change.error ? <p role="alert" className="text-sm text-danger">{change.error.message}</p> : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
        <button type="button" className="desk-button-ghost" onClick={onClose}>Cancel</button>
        <button type="submit" className="desk-button-primary" disabled={change.isPending}>{change.isPending ? "Saving…" : "Save"}</button>
      </div>
    </form>}
  </Modal>;
}
