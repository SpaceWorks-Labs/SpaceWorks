import { t } from "@lingui/core/macro";
import { ShieldCheck } from "lucide-react";
import { ErrorText, ListRow, Modal, StatusPill } from "../../../../components/ui";
import { MachineScopeChips } from "./MachineScopePicker";
import { needsMachineScope, roleNames, type StaffRoleRow, type StaffRolesPolicy } from "./staffRolesApi";

export function StaffRoleRows({ rows, policy, pending, onEdit, onRevoke, onRestore, onResetMfa }: {
  rows: StaffRoleRow[]; policy?: StaffRolesPolicy; pending: boolean;
  onEdit: (row: StaffRoleRow) => void; onRevoke: (row: StaffRoleRow) => void;
  onRestore: (row: StaffRoleRow) => void; onResetMfa: (row: StaffRoleRow) => void;
}) {
  return <div className="grid gap-3">{rows.map(row => {
    const name = row.display_name || row.username;
    return <ListRow key={row.id} title={name} identity={{ kind: "avatar", name, seed: String(row.user_id) }}
      meta={<span className="grid gap-1">
        <span>{row.username}{row.email ? ` · ${row.email}` : ""}</span>
        <span>{roleNames(policy, row.roles) || t`No roles`}</span>
        {needsMachineScope(policy, row.roles) ? (row.machine_types?.length || row.machines?.length
          ? <MachineScopeChips types={row.machine_types} machines={row.machines} />
          : <span className="text-danger">{t`No machines assigned`}</span>) : null}
        <span>{row.mfa_enabled ? t`Two-step sign-in on` : t`Two-step sign-in off`}</span>
        {row.status === "revoked" && row.revocation_reason ? <span>{t`Revoked: ${row.revocation_reason}`}</span> : null}
      </span>}
      right={<div className="flex flex-wrap items-center gap-2">
        <StatusPill label={row.status === "active" ? t`Active` : t`Revoked`} tone={row.status === "active" ? "success" : "neutral"} />
        {row.can.change_roles ? <button type="button" className="desk-button min-h-11" disabled={pending} onClick={() => onEdit(row)}>{t`Change roles`}</button> : null}
        {row.can.restore ? <button type="button" className="desk-button min-h-11" disabled={pending} onClick={() => onRestore(row)}>{t`Restore`}</button> : null}
        {row.can.reset_mfa ? <button type="button" className="desk-button inline-flex min-h-11 items-center gap-2" disabled={pending} onClick={() => onResetMfa(row)}>
          <ShieldCheck size={16} aria-hidden />{t`Reset authenticator`}</button> : null}
        {row.can.revoke ? <button type="button" className="desk-button-danger-outline min-h-11" disabled={pending} onClick={() => onRevoke(row)}>{t`Revoke`}</button> : null}
      </div>} />;
  })}</div>;
}

/** Confirms a revoke. The person keeps their account and member features; only this staff authority ends. */
export function StaffRevokeDialog({ row, reason, onReason, pending, error, onClose, onConfirm }: {
  row: StaffRoleRow; reason: string; onReason: (value: string) => void; pending: boolean;
  error?: string; onClose: () => void; onConfirm: () => void;
}) {
  const name = row.display_name || row.username;
  return <Modal open title={t`Revoke staff roles`} onClose={() => { if (!pending) onClose(); }}>
    <form className="grid gap-4" onSubmit={e => { e.preventDefault(); if (!pending) onConfirm(); }}>
      <p className="text-sm text-muted">{t`Revoke ${name}'s staff roles here? Their own account and member features keep working. You can restore the roles later.`}</p>
      <label className="grid gap-2 text-sm font-semibold text-ink">{t`Reason (optional)`}<textarea className="desk-input" maxLength={200} disabled={pending} value={reason} onChange={e => onReason(e.target.value)} />
      </label>
      {error ? <ErrorText message={error} /> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button" disabled={pending} onClick={onClose}>{t`Cancel`}</button>
        <button className="desk-button-danger" disabled={pending}>{pending ? t`Revoking…` : t`Revoke`}</button>
      </div>
    </form>
  </Modal>;
}
