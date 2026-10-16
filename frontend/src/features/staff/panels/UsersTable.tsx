import { useState } from "react";

import { Badge, EmptyState, Modal } from "../../../components/ui";
import type { StaffMembershipRow, StaffRole } from "./rolesApi";
import { RoleSetPicker } from "./RoleSetPicker";

export function UsersTable({ rows, makerspaceNames, loading, assignableRoles, onRestrict, onRestore, onResetPassword, onRevoke, onChangeRole, onMachineTypes }: {
  rows: StaffMembershipRow[];
  makerspaceNames: Map<number, string>;
  loading: boolean;
  assignableRoles: StaffRole[];
  onRestrict: (membership: StaffMembershipRow) => void;
  onRestore: (membership: StaffMembershipRow) => void;
  onResetPassword: (membership: StaffMembershipRow) => void;
  onRevoke: (membership: StaffMembershipRow) => void;
  onMachineTypes: (membershipId: number) => void;
  onChangeRole: (membership: StaffMembershipRow, roleIds: number[]) => Promise<unknown>;
}) {
  const [changeTarget, setChangeTarget] = useState<StaffMembershipRow | null>(null);
  const [roleIds, setRoleIds] = useState<number[]>([]);
  const [assignPending, setAssignPending] = useState(false);
  const [assignError, setAssignError] = useState("");
  const openChange = (membership: StaffMembershipRow) => {
    setAssignError("");
    setChangeTarget(membership);
    setRoleIds(membership.role_ids);
  };
  const submitChange = () => {
    if (!changeTarget || !roleIds.length) return;
    setAssignError("");
    setAssignPending(true);
    onChangeRole(changeTarget, roleIds)
      .then(() => setChangeTarget(null))
      .catch((error) => setAssignError(error instanceof Error ? error.message : "Unable to change role"))
      .finally(() => setAssignPending(false));
  };
  if (loading) return <p className="text-sm text-muted">Loading staff...</p>;
  if (!rows.length) return <EmptyState title="No staff" description="No memberships match this filter." />;
  return (
    <>
      <div className="overflow-x-auto rounded-md border border-line bg-bg">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead className="eyebrow bg-surface"><tr className="border-b border-line">{["Username", "Email", "Role", "Makerspace", "Access", ""].map((header) => <th scope={header ? "col" : undefined} key={header} className="px-3 py-2">{header}</th>)}</tr></thead>
          <tbody>{rows.map((membership) => <tr key={membership.id} className="border-b border-line last:border-b-0">
            <td className="px-3 py-2 font-semibold text-ink"><span className="block max-w-40 break-words">{membership.user.username}</span></td>
            <td className="px-3 py-2 text-muted"><span className="block max-w-56 break-all">{membership.user.email || "-"}</span></td>
            <td className="px-3 py-2 text-ink">{roleLabel(membership)}</td>
            <td className="px-3 py-2 text-ink">{makerspaceNames.get(membership.makerspace_id) ?? membership.makerspace_slug}</td>
            <td className="px-3 py-2"><AccessBadge status={membership.user.access_status} /></td>
            <td className="px-3 py-2"><div className="desk-actions flex flex-wrap justify-end gap-2">
              <button className="desk-button-ghost" type="button" disabled={!assignableRoles.length} onClick={() => openChange(membership)}>Change roles</button>
              {membership.status === "active" && membership.roles.some((role) => role.slug === "machine_manager") ? <button className="desk-button-ghost" type="button" onClick={() => onMachineTypes(membership.id)}>Machine types</button> : null}
              <button className="desk-button-danger" type="button" onClick={() => onRestrict(membership)}>Restrict</button>
              <button className="desk-button-warn" type="button" onClick={() => onResetPassword(membership)}>Reset password</button>
              <button className="desk-button-success" type="button" disabled={membership.user.access_status === "active"} onClick={() => onRestore(membership)}>Restore</button>
              <button className="desk-button-danger" type="button" onClick={() => onRevoke(membership)}>Revoke</button>
            </div></td>
          </tr>)}</tbody>
        </table>
      </div>
      <ChangeRoleModal target={changeTarget} roleIds={roleIds} roles={assignableRoles} pending={assignPending} error={assignError} onClose={() => setChangeTarget(null)} onChange={setRoleIds} onSubmit={submitChange} />
    </>
  );
}

function ChangeRoleModal({ target, roleIds, roles, pending, error, onClose, onChange, onSubmit }: {
  target: StaffMembershipRow | null;
  roleIds: number[];
  roles: StaffRole[];
  pending: boolean;
  error: string;
  onClose: () => void;
  onChange: (roleIds: number[]) => void;
  onSubmit: () => void;
}) {
  return <Modal open={Boolean(target)} onClose={onClose} title={target ? `Change roles for ${target.user.username}` : "Change roles"} footer={<div className="desk-actions flex justify-end gap-2"><button className="desk-button-ghost" type="button" disabled={pending} onClick={onClose}>Cancel</button><button className="desk-button-primary" type="button" disabled={!roleIds.length || pending || roleIds.some((id) => !roles.some((role) => role.id === id))} onClick={onSubmit}>{pending ? "Saving..." : "Save roles"}</button></div>}><div className="grid gap-2"><RoleSetPicker roles={roles} value={roleIds} onChange={onChange} disabled={pending} />{error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}</div></Modal>;
}

function AccessBadge({ status }: { status: string }) {
  const tone = status === "active" ? "success" : status === "restricted" ? "warn" : "danger";
  return <Badge tone={tone}>{status.replace(/_/g, " ")}</Badge>;
}

function roleLabel(membership: StaffMembershipRow) {
  return membership.roles.map((role) => role.name).join(" + ") || membership.role.replace(/_/g, " ");
}
