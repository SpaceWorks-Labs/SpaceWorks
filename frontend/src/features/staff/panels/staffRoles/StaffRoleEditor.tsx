import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ErrorText, Modal } from "../../../../components/ui";
import { RoleSetPicker } from "../RoleSetPicker";
import { changeStaffRole, staffRoleErrorText, type StaffRoleRow, type StaffRolesPolicy } from "./staffRolesApi";

export type RoleDraft = { roles: string[]; machine_type_ids: number[] };

/** A role set is valid when it is non-empty and an exclusive role (Space Manager) is held alone. */
export function validRoleSet(policy: StaffRolesPolicy, roles: string[]) {
  const exclusive = roles.some(slug => policy.grantable_roles.find(role => role.slug === slug)?.combinable === false);
  return roles.length > 0 && (!exclusive || roles.length === 1);
}

/** Role checkboxes plus the machine types a Machine Manager is limited to. */
export function StaffRoleFields({ policy, draft, onChange }: {
  policy: StaffRolesPolicy; draft: RoleDraft; onChange: (draft: RoleDraft) => void;
}) {
  const choices = policy.grantable_roles.map((role, index) => ({ id: index + 1, slug: role.slug, name: role.name, exclusive: !role.combinable }));
  return <>
    <RoleSetPicker roles={choices} value={choices.filter(role => draft.roles.includes(role.slug)).map(role => role.id)}
      onChange={ids => {
        const roles = choices.filter(role => ids.includes(role.id)).map(role => role.slug);
        onChange({ roles, machine_type_ids: roles.includes("machine_manager") ? draft.machine_type_ids : [] });
      }} />
    {draft.roles.includes("machine_manager") ? <fieldset className="grid gap-2">
      <legend className="text-sm font-semibold text-ink">{t`Assigned machine types`}</legend>
      <p className="text-sm text-muted">{t`No selected types means no machines. A type includes machines added to it later.`}</p>
      {policy.machine_types.length ? policy.machine_types.map(type => <label key={type.id} className="flex min-h-11 items-center gap-3 text-sm">
        <input type="checkbox" className="h-5 w-5 accent-accent" checked={draft.machine_type_ids.includes(type.id)} onChange={e => onChange({ ...draft,
          machine_type_ids: e.target.checked ? [...draft.machine_type_ids, type.id] : draft.machine_type_ids.filter(id => id !== type.id),
        })} />{type.name}
      </label>) : <p className="text-sm text-muted">{t`This makerspace has no machine types yet.`}</p>}
    </fieldset> : null}
  </>;
}

export function StaffRoleEditor({ space, policy, row, onClose, onSaved }: {
  space: number; policy: StaffRolesPolicy; row: StaffRoleRow; onClose: () => void; onSaved: (row: StaffRoleRow) => void;
}) {
  const [draft, setDraft] = useState<RoleDraft>({ roles: row.roles, machine_type_ids: row.machine_type_ids });
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
  </Modal>;
}
