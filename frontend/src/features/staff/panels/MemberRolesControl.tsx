import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CollapsibleSection, ErrorText, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { RoleSetPicker } from "./RoleSetPicker";
import { MemberMachineTypes } from "./MemberMachineTypes";
import { refreshMembershipAuthority, type MembershipRoles } from "./roleSets";
import type { StaffRole } from "./rolesApi";
import { BoxArt } from "../../../components/BoxSpinner";

/** A member's current roles, an editor for the whole set, and the per-person machine types for a Machine Manager. */
export function MemberRolesControl({ msId, membershipId, membership, roles, onAuthRefresh }: {
  msId: number;
  membershipId: number;
  membership: MembershipRoles;
  roles: StaffRole[];
  onAuthRefresh: () => void;
}) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
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
      setOpen(false);
      void refreshMembershipAuthority(client, msId);
      onAuthRefresh();
      if (firstMachineRole) setMachineOpen(true);
    },
  });
  const isMachineManager = membership.roles.some((role) => role.slug === "machine_manager");
  return <div className="grid min-w-0 gap-3">
    <div className="flex flex-wrap items-center gap-2">
      {membership.roles.length ? membership.roles.map((role) => <StatusPill key={role.id} label={role.name} tone="accent" />) : <StatusPill label={t`Member`} />}
      {isMachineManager ? <button className="desk-button" type="button" onClick={() => setMachineOpen(true)}>{t`Machine types`}</button> : null}
    </div>
    <CollapsibleSection title={t`Change roles`} open={open} onToggle={() => setOpen((value) => !value)}>
      <div className="grid gap-3 p-3">
        <RoleSetPicker roles={roles} value={ids} onChange={setDraft} disabled={save.isPending} />
        {save.error ? <ErrorText message={save.error.message} /> : null}
        <div className="desk-actions flex flex-wrap justify-end gap-2">
          {draft !== null ? <button className="desk-button-ghost" type="button" disabled={save.isPending} onClick={() => { setDraft(null); save.reset(); }}>{t`Discard`}</button> : null}
          <button className="desk-button-primary" type="button" disabled={save.isPending || !ids.length || draft === null || ids.some((id) => !roles.some((role) => role.id === id))} onClick={() => save.mutate()}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save roles`}</button>
        </div>
      </div>
    </CollapsibleSection>
    {machineOpen ? <MemberMachineTypes msId={msId} membershipId={membershipId} onAuthRefresh={onAuthRefresh} onClose={() => setMachineOpen(false)} /> : null}
  </div>;
}
