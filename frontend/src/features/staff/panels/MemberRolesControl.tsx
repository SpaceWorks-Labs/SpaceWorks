import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { RoleSetPicker } from "./RoleSetPicker";
import { MemberMachineTypes } from "./MemberMachineTypes";
import { refreshMembershipAuthority, type MembershipRoles } from "./roleSets";
import type { StaffRole } from "./rolesApi";

export function MemberRolesControl({ msId, membershipId, membership, roles, onAuthRefresh }: {
  msId: number;
  membershipId: number;
  membership: MembershipRoles;
  roles: StaffRole[];
  onAuthRefresh: () => void;
}) {
  const client = useQueryClient();
  const [draft, setDraft] = useState<number[] | null>(null);
  const ids = draft ?? membership.role_ids;
  const [machineOpen, setMachineOpen] = useState(false);
  const save = useMutation({
    mutationFn: () => staffRequest<MembershipRoles>(`/admin/memberships/${membershipId}/role`, {
      method: "PATCH", body: JSON.stringify({ role_ids: ids }),
    }),
    onSuccess: (updated) => {
      const firstMachineRole = updated.roles.some((role) => role.slug === "machine_manager")
        && !membership.roles.some((role) => role.slug === "machine_manager");
      setDraft(null);
      void refreshMembershipAuthority(client, msId);
      onAuthRefresh();
      if (firstMachineRole) setMachineOpen(true);
    },
  });
  return <div className="grid gap-2">
    <details className="rounded border border-line p-2">
      <summary className="min-h-11 cursor-pointer text-sm text-ink">Change roles</summary>
      <RoleSetPicker roles={roles} value={ids} onChange={setDraft} disabled={save.isPending} />
      <button className="desk-button-primary" type="button" disabled={save.isPending || !ids.length || draft === null || ids.some((id) => !roles.some((role) => role.id === id))} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Save roles"}</button>
      {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
    </details>
    {membership.roles.some((role) => role.slug === "machine_manager") ? <button className="desk-button-ghost" type="button" onClick={() => setMachineOpen(true)}>Machine types</button> : null}
    {machineOpen ? <MemberMachineTypes msId={msId} membershipId={membershipId} onAuthRefresh={onAuthRefresh} onClose={() => setMachineOpen(false)} /> : null}
  </div>;
}
