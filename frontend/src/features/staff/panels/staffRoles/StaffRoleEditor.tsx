import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ErrorText, Modal } from "../../../../components/ui";
import { RoleSetPicker } from "../RoleSetPicker";
import { MachineScopePicker } from "./MachineScopePicker";
import { StaffUnitScopeField } from "../../units/StaffUnitScopeField";
import { changeStaffRole, needsMachineScope, staffRoleErrorText, type StaffRoleRow, type StaffRolesPolicy } from "./staffRolesApi";

export type RoleDraft = { roles: string[]; machine_type_ids: number[]; machine_ids: number[] };

/** A role set is valid when it is non-empty and an exclusive role (Space Manager) is held alone. */
export function validRoleSet(policy: StaffRolesPolicy, roles: string[]) {
  const exclusive = roles.some(slug => policy.grantable_roles.find(role => role.slug === slug)?.combinable === false);
  return roles.length > 0 && (!exclusive || roles.length === 1);
}

/** Role checkboxes (Space Manager alone, the rest combine) plus, for a Machine Manager or Technician, which machines. */
export function StaffRoleFields({ policy, draft, onChange }: {
  policy: StaffRolesPolicy; draft: RoleDraft; onChange: (draft: RoleDraft) => void;
}) {
  const choices = policy.grantable_roles.map((role, index) => ({ id: index + 1, slug: role.slug, name: role.name, exclusive: !role.combinable }));
  return <>
    <RoleSetPicker roles={choices} value={choices.filter(role => draft.roles.includes(role.slug)).map(role => role.id)}
      onChange={ids => {
        const roles = choices.filter(role => ids.includes(role.id)).map(role => role.slug);
        // A scope only means something for the scoped roles; dropping the last of them clears it.
        onChange(needsMachineScope(policy, roles) ? { ...draft, roles } : { roles, machine_type_ids: [], machine_ids: [] });
      }} />
    {needsMachineScope(policy, draft.roles) ? <MachineScopePicker types={policy.machine_types} machines={policy.machines ?? []}
      value={draft} onChange={scope => onChange({ ...draft, ...scope })} /> : null}
  </>;
}

export function StaffRoleEditor({ space, policy, row, onClose, onSaved }: {
  space: number; policy: StaffRolesPolicy; row: StaffRoleRow; onClose: () => void; onSaved: (row: StaffRoleRow) => void;
}) {
  const [draft, setDraft] = useState<RoleDraft>({ roles: row.roles, machine_type_ids: row.machine_type_ids, machine_ids: row.machine_ids ?? [] });
  const save = useMutation({
    mutationFn: () => changeStaffRole(space, row.id, draft),
    onSuccess: onSaved,
  });
  const valid = validRoleSet(policy, draft.roles);
  const name = row.display_name || row.username;
  return <Modal open size="xl" title={t`Roles for ${name}`} onClose={() => { if (!save.isPending) onClose(); }}>
    <form className="grid gap-4" onSubmit={e => { e.preventDefault(); if (valid && !save.isPending) save.mutate(); }}>
      <fieldset disabled={save.isPending} className="grid min-w-0 gap-4">
        <legend className="sr-only">{t`Staff roles for ${name}`}</legend>
        <StaffRoleFields policy={policy} draft={draft} onChange={setDraft} />
      </fieldset>
      {save.error ? <ErrorText message={staffRoleErrorText(save.error)} /> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button" disabled={save.isPending} onClick={onClose}>{t`Cancel`}</button>
        <button className="desk-button-primary" disabled={save.isPending || !valid}>{save.isPending ? t`Saving…` : t`Save roles`}</button>
      </div>
    </form>
    {/* Parity O-F1: a unit limit is saved on its own and shows only while `membership.unit_scoped_staff` is on. */}
    <StaffUnitScopeField makerspaceId={space} membershipId={row.id} name={name} />
  </Modal>;
}
