import { useId, useState } from "react";

import { Modal } from "../../components/ui";

/** Reject (reason required) or cancel (reason optional) with text the requester will see. */
export function BookingDecisionDialog({ action, bookerName, open, pending, onCancel, onConfirm }: {
  action: "reject" | "cancel";
  bookerName: string;
  open: boolean;
  pending: boolean;
  onCancel: () => void;
  onConfirm: (reason: string) => void;
}) {
  const id = useId();
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const required = action === "reject";
  const missing = required && !reason.trim();
  const title = action === "reject" ? "Reject booking request" : "Cancel booking";
  const close = () => { setReason(""); setTouched(false); onCancel(); };
  return (
    <Modal open={open} onClose={close} title={title} footer={<div className="flex flex-wrap justify-end gap-2">
      <button type="button" className="desk-button-ghost min-h-11" onClick={close} disabled={pending}>Keep booking</button>
      <button type="submit" form={`${id}-form`} className="desk-button-danger min-h-11" disabled={pending}>
        {pending ? "Saving…" : title}
      </button>
    </div>}>
      <form id={`${id}-form`} className="grid gap-3" noValidate onSubmit={event => {
        event.preventDefault(); setTouched(true);
        if (!missing) { onConfirm(reason.trim()); setReason(""); setTouched(false); }
      }}>
        <p className="text-sm">{action === "reject" ? `Tell ${bookerName} why this request can't be approved.` : `Cancel the booking for ${bookerName}.`}</p>
        <label htmlFor={`${id}-reason`} className="grid gap-1 text-sm">
          <span>Reason{required ? " (required)" : " (optional)"} — shown to the requester</span>
          <textarea id={`${id}-reason`} className="desk-input min-h-24" maxLength={1000} value={reason}
            aria-invalid={touched && missing} onChange={event => setReason(event.target.value)} />
        </label>
        {touched && missing ? <p className="text-sm text-danger">Add a reason so the requester knows what to do next.</p> : null}
      </form>
    </Modal>
  );
}
