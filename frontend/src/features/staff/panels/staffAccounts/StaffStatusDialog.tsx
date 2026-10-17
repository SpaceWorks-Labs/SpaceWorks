import { ErrorText, Modal } from "../../../../components/ui";
import type { StaffAccount } from "../../../../lib/api/staffAccounts";

export function StaffStatusDialog({ account, pending, reason, onReason, error, onClose, onConfirm }: {
  account: StaffAccount; pending: boolean; reason: string; onReason: (value: string) => void;
  error?: Error | null; onClose: () => void; onConfirm: () => void;
}) {
  const action = account.is_active ? "Deactivate" : "Reactivate";
  return <Modal open title={`${action} staff account`} onClose={() => { if (!pending) onClose(); }}>
    <form className="grid gap-4" onSubmit={e => { e.preventDefault(); if (!pending) onConfirm(); }}>
      <p className="text-sm text-muted">{account.is_active
        ? `Deactivate ${account.display_name || account.username}? Existing sessions and invitations will be revoked. History is kept.`
        : `Reactivate ${account.display_name || account.username}? Previous sessions and invitations stay revoked. Issue a new password to restore sign-in.`}</p>
      {account.is_active ? <label className="grid gap-2 text-sm font-semibold">Reason (optional)<textarea className="desk-input" maxLength={1000} disabled={pending} value={reason} onChange={e => onReason(e.target.value)} /></label> : null}
      {error ? <ErrorText message={error.message} /> : null}
      <div className="flex justify-end gap-2"><button type="button" className="desk-button" disabled={pending} onClick={onClose}>Cancel</button>
        <button className={account.is_active ? "desk-button-danger" : "desk-button-primary"} disabled={pending}>{pending ? "Saving…" : action}</button></div>
    </form>
  </Modal>;
}
