import { useState } from "react";
import { Modal } from "../../../components/ui/Modal";
import { Field } from "../../../components/ui/Field";
import { commandError, type EventScope } from "../../events/stagedForms/privateQueries";
import { utcInstant } from "../../events/stagedForms/formPayload";
import { reimbursementAdminPath, useClaimReviewCommand } from "./api";
import type { AllocationCommand, ClaimReviewDetail } from "./types";
type Action = "extend" | "attendance-attestations" | "receipt-allocation-overrides";
export function ClaimFinanceAction({ scope, row, action, onClose }: { scope: EventScope; row: ClaimReviewDetail; action: Action; onClose: () => void }) {
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [when, setWhen] = useState("");
  const [evidence, setEvidence] = useState("");
  const [lineId, setLineId] = useState(row.lines[0]?.line_uuid ?? "");
  const [total, setTotal] = useState("");
  const [allocations, setAllocations] = useState<AllocationCommand["allocations"]>([]);
  const [error, setError] = useState("");
  const mutation = useClaimReviewCommand(scope);
  const line = row.lines.find(item => item.line_uuid === lineId);
  const title = action === "extend" ? "Extend claim deadline" : action === "attendance-attestations" ? "Exceptional attendance attestation" : "Receipt allocation override";
  const dirty = Boolean(reason || note || when || evidence || total || allocations.length || lineId !== row.lines[0]?.line_uuid);
  return <Modal open title={title} onClose={() => { if (!mutation.isPending && (!dirty || window.confirm("Discard this unsaved finance action?"))) onClose(); }}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault();
      try {
        const common = { expected_version: row.version, reason_code: reason, note: note.trim() };
        if (action === "extend") {
          const due_at = utcInstant(when); if (Date.parse(due_at) <= Date.now()) throw new Error("Choose a future deadline.");
          mutation.mutate({ path: `${reimbursementAdminPath(scope)}claims/${row.id}/${action}/`, body: { ...common, due_revision: row.due_revision, due_at } }, { onSuccess: onClose });
        } else if (action === "attendance-attestations") {
          const refs = evidence.split(",").map(value => Number(value.trim()));
          if (refs.some(id => !Number.isSafeInteger(id) || id < 1)) throw new Error("Enter positive evidence reference IDs.");
          mutation.mutate({ path: `${reimbursementAdminPath(scope)}claims/${row.id}/${action}/`, body: { ...common, registration_id: row.registration_id,
            expected_attendance_revision: row.attendance_revision, attended_at: utcInstant(when), venue_evidence_refs: refs } }, { onSuccess: onClose });
        } else if (line) {
          if (!allocations.length || !Number.isSafeInteger(Number(total)) || Number(total) < 1) throw new Error("Enter the receipt total and allocations.");
          mutation.mutate({ path: `${reimbursementAdminPath(scope)}claims/${row.id}/${action}/`, body: { ...common, asset_id: line.receipt_asset_id,
            expected_receipt_use_version: line.receipt_use_version, receipt_total_minor: Number(total), original_currency: line.original_currency, allocations } }, { onSuccess: onClose });
        }
      } catch (failure) { setError(failure instanceof Error ? failure.message : "Check these fields."); }
    }}><p>{action === "attendance-attestations" ? "Record evidence of venue attendance for this claim. A later attendance correction invalidates this attestation. Holds need separate review." : action === "receipt-allocation-overrides" ? "Allocate the original receipt amount across authorized same-host claim lines. The combined amount cannot exceed the receipt total." : "The owner will be notified of the new deadline."}</p>
      <fieldset disabled={mutation.isPending} className="grid gap-4"><legend className="sr-only">Finance action details</legend>
        {action !== "receipt-allocation-overrides" ? <Field label={action === "extend" ? "New due time (your local time)" : "Attended at (your local time)"}><input className="desk-input" type="datetime-local" required value={when} onChange={event => setWhen(event.target.value)} /></Field> : <>
          <Field label="Receipt from claim expense"><select className="desk-input" required value={lineId} onChange={event => { setLineId(event.target.value); setAllocations([]); }}>{row.lines.map((item, index) => <option key={item.line_uuid} value={item.line_uuid}>Expense {index + 1} · {item.category}</option>)}</select></Field>
          <Field label="Full receipt total (original minor units)"><input className="desk-input" required type="number" min={1} step={1} max={9000000000000000} value={total} onChange={event => setTotal(event.target.value)} /></Field>
          {allocations.map((allocation, index) => <div key={index} className="grid gap-3 rounded-xl border border-line p-3">
            <Field label={`Claim UUID for allocation ${index + 1}`}><input className="desk-input" required value={allocation.claim_uuid} onChange={event => setAllocations(allocations.map((value, i) => i === index ? { ...value, claim_uuid: event.target.value } : value))} /></Field>
            <Field label={`Line UUID for allocation ${index + 1}`}><input className="desk-input" required value={allocation.line_uuid} onChange={event => setAllocations(allocations.map((value, i) => i === index ? { ...value, line_uuid: event.target.value } : value))} /></Field>
            <Field label={`Original minor units for allocation ${index + 1}`}><input className="desk-input" type="number" required min={1} step={1} value={allocation.original_amount_minor} onChange={event => setAllocations(allocations.map((value, i) => i === index ? { ...value, original_amount_minor: event.target.valueAsNumber } : value))} /></Field>
            <button type="button" className="desk-button" onClick={() => setAllocations(allocations.filter((_, i) => i !== index))}>Remove allocation</button></div>)}
          <button type="button" className="desk-button" onClick={() => setAllocations([...allocations, { claim_uuid: row.uuid, line_uuid: lineId, original_amount_minor: line?.original_amount_minor ?? 1 }])}>Add allocation</button></>}
        {action === "attendance-attestations" ? <Field label="Venue evidence reference IDs" hint="Comma separated IDs of authorized venue evidence."><input className="desk-input" required value={evidence} onChange={event => setEvidence(event.target.value)} /></Field> : null}
        <Field label="Reason code"><input className="desk-input" required maxLength={64} pattern="[a-z][a-z0-9_]{0,63}" value={reason} onChange={event => setReason(event.target.value)} /></Field>
        <Field label="Finance note"><textarea className="desk-input" required rows={3} maxLength={5000} value={note} onChange={event => setNote(event.target.value)} /></Field>
        <button type="submit" className="desk-button-primary">{mutation.isPending ? "Recording…" : "Confirm and record"}</button></fieldset>
      {error || mutation.error ? <p role="alert">{error || commandError(mutation.error)}</p> : null}
    </form></Modal>;
}
