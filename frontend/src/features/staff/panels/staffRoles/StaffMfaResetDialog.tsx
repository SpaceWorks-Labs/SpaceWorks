import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ErrorText, Field, Modal } from "../../../../components/ui";
import { resetStaffMfa, staffRoleErrorText, type StaffRoleRow } from "./staffRolesApi";

/** Clears the person's authenticator, passkeys and recovery codes and ends their sessions. The reason is audited. */
export function StaffMfaResetDialog({ space, row, onClose, onDone }: {
  space: number; row: StaffRoleRow; onClose: () => void; onDone: () => void;
}) {
  const [reason, setReason] = useState("");
  const reset = useMutation({ mutationFn: () => resetStaffMfa(space, row.id, reason.trim()), onSuccess: onDone });
  const valid = reason.trim().length >= 3 && reason.trim().length <= 300;
  const name = row.display_name || row.username;
  return <Modal open title={t`Reset authenticator`} onClose={() => { if (!reset.isPending) onClose(); }}>
    <form className="grid gap-4" onSubmit={e => { e.preventDefault(); if (valid && !reset.isPending) reset.mutate(); }}>
      <p className="text-sm text-muted">{t`This clears ${name}'s authenticator app, passkeys and recovery codes, and signs them out everywhere. They set up two-step sign-in again the next time they sign in.`}</p>
      <Field label={t`Reason`} hint={t`Required, 3 to 300 characters. Kept in the audit log.`}>
        <textarea className="desk-input" required minLength={3} maxLength={300} disabled={reset.isPending}
          value={reason} onChange={e => setReason(e.target.value)} />
      </Field>
      {reset.error ? <ErrorText message={staffRoleErrorText(reset.error)} /> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button" disabled={reset.isPending} onClick={onClose}>{t`Cancel`}</button>
        <button className="desk-button-danger" disabled={reset.isPending || !valid}>{reset.isPending ? t`Resetting…` : t`Reset authenticator`}</button>
      </div>
    </form>
  </Modal>;
}
