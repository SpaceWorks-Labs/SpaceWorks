import { t } from "@lingui/core/macro";
import { RequestFlowDialog } from "./RequestFlowDialog";
import { useEffect, useState } from "react";

import { ErrorText } from "../../../components/ui";
import { formatLocale } from "../../../lib/format";
import { submitForm } from "./QueuesModalShared";
import type { FormModalProps, RejectRequestValues, ReturnDueValues } from "./QueuesModalTypes";

export type {
  AssignIssueValues,
  IssueReject,
  RejectRequestValues,
  ReturnDueValues,
  ReturnRequestValues,
} from "./QueuesModalTypes";
export { AssignIssueModal } from "./QueuesAssignIssueModal";
export { ReturnRequestModal } from "./QueuesReturnRequestModal";

export type ReturnDueNotice = { code: "space_closed"; next_open_at: string | null };

/** The server's warning for a staff-entered due that falls while the space is closed. */
export function returnDueNoticeText(notice: ReturnDueNotice, timeZone?: string) {
  if (!notice.next_open_at) return t`Space is closed at this time and has no upcoming opening.`;
  const next = new Date(notice.next_open_at).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short", timeZone });
  return t`Space is closed at this time — next open ${next}.`;
}

export function ReturnDueModal({
  row,
  open,
  pending,
  error,
  defaultValue,
  notice,
  timeZone,
  onClose,
  onSubmit,
}: FormModalProps<ReturnDueValues> & { defaultValue: string; notice?: ReturnDueNotice | null; timeZone?: string }) {
  const [returnDueAt, setReturnDueAt] = useState(defaultValue);
  // The notice describes the saved value; hide it once staff edit the field.
  const [edited, setEdited] = useState(false);

  useEffect(() => {
    if (open) setReturnDueAt(defaultValue);
  }, [defaultValue, open]);
  useEffect(() => setEdited(false), [notice, open]);

  return (
    <RequestFlowDialog open={open} onClose={onClose} title={row ? t`Set due for request #${row.id}` : t`Set due`} formId="return-due-form" pending={pending} submitLabel={t`Save due date`}>
      <form id="return-due-form" className="grid gap-3" onSubmit={(event) => submitForm(event, () => onSubmit({ returnDueAt }))}>
        <label className="grid gap-1 text-sm">
          <span className="font-medium text-ink">{t`Return due date and time`}</span>
          <input className="desk-input" type="datetime-local" value={returnDueAt} disabled={pending} onChange={(event) => { setReturnDueAt(event.target.value); setEdited(true); }} />
        </label>
        {notice && !edited ? <p role="status" className="text-sm text-warn-ink">{returnDueNoticeText(notice, timeZone)}</p> : null}
        <ErrorText message={error} />
      </form>
    </RequestFlowDialog>
  );
}

export function RejectRequestModal({ row, open, pending, error, onClose, onSubmit }: FormModalProps<RejectRequestValues>) {
  const [reason, setReason] = useState("");
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    if (open) {
      setReason("");
      setValidationError("");
    }
  }, [open]);

  return (
    <RequestFlowDialog open={open} onClose={onClose} title={row ? t`Reject request #${row.id}` : t`Reject request`} formId="reject-request-form" pending={pending} submitLabel={t`Reject request`} danger>
      <form id="reject-request-form" className="grid gap-3" onSubmit={(event) => submitForm(event, submitReject)}>
        <label className="grid gap-1 text-sm">
          <span className="font-medium text-ink">{t`Reason`}</span>
          <textarea className="desk-input min-h-24 w-full resize-y" value={reason} disabled={pending} onChange={(event) => setReason(event.target.value)} />
        </label>
        <ErrorText message={validationError || error} />
      </form>
    </RequestFlowDialog>
  );

  function submitReject() {
    if (!reason.trim()) return setValidationError(t`Reason is required.`);
    onSubmit({ reason: reason.trim() });
  }
}
