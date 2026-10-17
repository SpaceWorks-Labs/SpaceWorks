import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ErrorText, Modal } from "../../../../components/ui";
import { createStaffAccount, updateStaffAccount, type StaffAccount, type StaffAccountDraft, type StaffAccountPolicy, type StaffRoleKey } from "../../../../lib/api/staffAccounts";
import { StaffAccountFields } from "./StaffAccountFields";

export function StaffAccountEditor({ space, policy, account, initialRoles = [], onClose, onSaved }: {
  space: number; policy: StaffAccountPolicy; account?: StaffAccount; onClose: () => void;
  initialRoles?: StaffRoleKey[];
  onSaved: (account: StaffAccount, invitationSent?: boolean) => void;
}) {
  const [draft, setDraft] = useState<StaffAccountDraft>(() => account ? {
    display_name: account.display_name, roles: account.roles, machine_type_ids: account.machine_type_ids,
  } : { display_name: "", email: "", username: "", roles: initialRoles.filter(role => policy.creatable_roles.includes(role) && (role !== "space_manager" || policy.can_manage_space_managers)), machine_type_ids: [] });
  const save = useMutation({ mutationFn: async () => {
    if (!draft.roles.length || (draft.roles.includes("space_manager") && draft.roles.length !== 1)) throw new Error("Choose a valid role set.");
    if (account) return { account: await updateStaffAccount(space, account.id, { roles: draft.roles, machine_type_ids: draft.machine_type_ids }) };
    if (!draft.display_name.trim() || (!draft.email?.trim() && !draft.username?.trim())) throw new Error("Provide a name and an email or username.");
    return createStaffAccount(space, { ...draft, display_name: draft.display_name.trim(), email: draft.email?.trim() || undefined, username: draft.username?.trim() || undefined });
  }, onSuccess: result => onSaved(result.account, "invitation_sent" in result ? result.invitation_sent : undefined) });
  const roles = policy.creatable_roles.filter(role => role !== "space_manager" || policy.can_manage_space_managers);
  return <Modal open size="xl" title={account ? `Roles for ${account.display_name || account.username}` : "Create staff account"} onClose={() => { if (!save.isPending) onClose(); }}>
    <form className="grid gap-4" onSubmit={e => { e.preventDefault(); if (!save.isPending) save.mutate(); }}>
      <StaffAccountFields space={space} draft={draft} onChange={setDraft} roles={roles} identity={!account} pending={save.isPending} />
      {!account ? <p className="text-sm text-muted">{policy.email_onboarding_available ? "An email invitation sets the initial password. You can also issue a password directly." : "Email onboarding is unavailable. Issue a password after creating the account."}</p> : null}
      {save.error ? <ErrorText message={save.error.message} /> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button" disabled={save.isPending} onClick={onClose}>Cancel</button>
        <button className="desk-button-primary" disabled={save.isPending || !draft.roles.length}>{save.isPending ? "Saving…" : account ? "Save roles" : "Create staff account"}</button>
      </div>
    </form>
  </Modal>;
}
