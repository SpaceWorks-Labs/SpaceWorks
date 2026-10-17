import { ListRow, StatusPill } from "../../../../components/ui";
import { STAFF_ROLE_NAMES, type StaffAccount } from "../../../../lib/api/staffAccounts";

export function StaffAccountRows({ rows, pending, onEdit, onPassword, onStatus, onResend }: {
  rows: StaffAccount[]; pending: boolean; onEdit: (account: StaffAccount) => void;
  onPassword: (account: StaffAccount) => void; onStatus: (account: StaffAccount) => void;
  onResend: (account: StaffAccount) => void;
}) {
  return <div className="grid gap-3">{rows.map(account => <ListRow key={account.id}
    title={account.display_name || account.username} identity={{ kind: "avatar", name: account.display_name || account.username, seed: String(account.id) }}
    meta={<div className="grid gap-1"><span>{account.username}{account.email ? ` · ${account.email}` : ""}</span>
      <span>{account.roles.map(role => STAFF_ROLE_NAMES[role]).join(" + ")}</span>
      <span>{account.mfa_enabled ? "Authenticator enabled" : "Authenticator not enrolled"}{account.must_change_password ? " · Password change required" : ""}</span></div>}
    right={<div className="flex flex-wrap items-center gap-2">
      <StatusPill label={account.is_active ? "Active" : "Inactive"} tone={account.is_active ? "success" : "neutral"} />
      {account.invitation_pending ? <StatusPill label="Invitation pending" tone="neutral" /> : null}
      {account.can.change_roles ? <button className="desk-button" disabled={pending} onClick={() => onEdit(account)}>Edit roles</button> : null}
      {account.can.set_password ? <button className="desk-button" disabled={pending} onClick={() => onPassword(account)}>Set password</button> : null}
      {account.can.resend_invite ? <button className="desk-button" disabled={pending} onClick={() => onResend(account)}>Resend invite</button> : null}
      {account.can.deactivate ? <button className="desk-button-danger-outline" disabled={pending} onClick={() => onStatus(account)}>Deactivate</button> : null}
      {account.can.reactivate ? <button className="desk-button" disabled={pending} onClick={() => onStatus(account)}>Reactivate</button> : null}
    </div>} />)}</div>;
}
