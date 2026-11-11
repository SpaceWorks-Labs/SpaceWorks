import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Field, Modal } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { lifecycleApi } from "../membershipLifecycleApi";

const REFUSALS: Record<string, () => string> = {
  membership_changes_already_asked: () => t`This application was already sent back once. Approve or decline it instead.`,
  membership_changes_not_allowed: () => t`Only an application still waiting for a decision can be sent back.`,
  membership_changes_not_for_staff: () => t`Staff invitations cannot be sent back for changes.`,
};

export function requestChangesErrorText(error: unknown) {
  if (error instanceof StructuredApiError) return REFUSALS[error.code ?? ""]?.() ?? error.message;
  return t`That did not work. Try again.`;
}

/**
 * Parity O-B2: send a join application back to the applicant with a note. Once per application:
 * they edit their answers and resubmit, and it returns to this queue. The note is shown to them as written.
 */
export function RequestChangesDialog({ makerspaceId, requestId, applicant, onClose, onDone }: {
  makerspaceId: number; requestId: number; applicant: string; onClose: () => void; onDone: () => void;
}) {
  const [reason, setReason] = useState("");
  const send = useMutation({
    mutationFn: () => lifecycleApi.requestChanges(makerspaceId, requestId, reason.trim()),
    onSuccess: () => { onDone(); onClose(); },
  });
  const close = () => { if (!send.isPending) onClose(); };
  return <Modal open onClose={close} title={t`Ask ${applicant} for changes`}
    footer={<div className="flex flex-wrap justify-end gap-2">
      <button className="desk-button" type="button" disabled={send.isPending} onClick={close}>{t`Cancel`}</button>
      <button className="desk-button-primary" type="button" disabled={send.isPending || !reason.trim()} onClick={() => send.mutate()}>
        {send.isPending ? t`Sending…` : t`Send back for changes`}</button>
    </div>}>
    <div className="grid gap-3">
      <p className="text-sm text-muted">{t`They get your note by notification, edit their answers and send the application back once. Its expiry restarts so they have time.`}</p>
      <Field label={t`What should they change?`} hint={t`Shown to the applicant exactly as written. Up to 1000 characters.`}>
        <textarea className="desk-input min-h-24" maxLength={1000} value={reason} autoFocus onChange={(event) => { setReason(event.target.value); send.reset(); }} />
      </Field>
      {send.error ? <p role="alert" className="text-sm text-danger">{requestChangesErrorText(send.error)}</p> : null}
    </div>
  </Modal>;
}
