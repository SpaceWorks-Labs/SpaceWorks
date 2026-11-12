import { t } from "@lingui/core/macro";
import { useState } from "react";

import { EmptyState, ErrorText, ListRow, Modal, OverflowMenu, StatusPill } from "../../../components/ui";
import type { StaffMembershipRow, StaffRole } from "./rolesApi";
import { RoleSetPicker } from "./RoleSetPicker";
import { membershipRoleLabel } from "../../members/membershipLabels";
import { LogoLoader } from "../../../components/LogoLoader";
import { BoxArt } from "../../../components/BoxSpinner";

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
      .catch((error) => setAssignError(error instanceof Error ? error.message : t`Unable to change role`))
      .finally(() => setAssignPending(false));
  };
  if (loading) return <LogoLoader label={t`Loading staff...`} size={48} className="min-h-16 py-3" />;
  if (!rows.length) return <EmptyState title={t`No staff`} description={t`No memberships match this filter.`} />;
  return (
    <>
      <div className="grid gap-3">{rows.map(membership => <ListRow key={membership.id}
        title={membership.user.username} identity={{ kind: "avatar", name: membership.user.username, seed: String(membership.user.id) }}
        meta={<><span className="[overflow-wrap:anywhere]">{membership.user.email || t`No email`}</span> · {roleLabel(membership)} · {makerspaceNames.get(membership.makerspace_id) ?? membership.makerspace_slug}</>}
        right={<div className="flex flex-wrap items-center gap-3"><AccessBadge status={membership.user.access_status} />
          {membership.user.access_status !== "active" ? <button className="desk-button" type="button" onClick={() => onRestore(membership)}>{t`Restore`}</button> : null}
          <button className="desk-button" type="button" disabled={!assignableRoles.length} onClick={() => openChange(membership)}>{t`Change roles`}</button>
          <OverflowMenu label={t`Actions for ${membership.user.username}`} actions={[
            // Machine Manager reach is per person: the machine types picked here.
            ...(membership.status === "active" && membership.roles.some((role) => role.slug === "machine_manager") ? [{ label: t`Machine types`, onClick: () => onMachineTypes(membership.id) }] : []),
            { label: t`Restrict`, tone: "danger", onClick: () => onRestrict(membership) },
            { label: t`Reset password`, onClick: () => onResetPassword(membership) },
            { label: t`Revoke`, tone: "danger", onClick: () => onRevoke(membership) },
          ]} />
        </div>} />)}</div>
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
  return <Modal open={Boolean(target)} onClose={onClose} title={target ? t`Change roles for ${target.user.username}` : t`Change roles`}
    footer={<div className="desk-actions flex flex-wrap justify-end gap-2"><button className="desk-button-ghost" type="button" disabled={pending} onClick={onClose}>{t`Cancel`}</button>
      <button className="desk-button-primary" type="button" disabled={!roleIds.length || pending || roleIds.some((id) => !roles.some((role) => role.id === id))} onClick={onSubmit}>{pending ? <><BoxArt size={16} mono />{t`Saving...`}</> : t`Save roles`}</button></div>}>
    <div className="grid gap-3"><RoleSetPicker roles={roles} value={roleIds} onChange={onChange} disabled={pending} />{error ? <ErrorText message={error} /> : null}</div>
  </Modal>;
}

function AccessBadge({ status }: { status: string }) {
  const tone = status === "active" ? "success" : status === "restricted" ? "warn" : "danger";
  return <StatusPill tone={tone} label={status === "active" ? t`Active` : status === "restricted" ? t`Restricted` : status === "suspended" ? t`Suspended` : status.replace(/_/g, " ")} />;
}

function roleLabel(membership: StaffMembershipRow) {
  return membership.roles.map((role) => role.name).join(" + ") || membershipRoleLabel(membership.role);
}
