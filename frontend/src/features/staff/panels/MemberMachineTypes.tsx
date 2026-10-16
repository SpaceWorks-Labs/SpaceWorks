import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Modal } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { getMemberMachineScope, setMemberMachineScope, type MemberMachineScope } from "./rolesApi";
import { refreshMembershipAuthority } from "./roleSets";

export function MemberMachineTypes({ msId, membershipId, onAuthRefresh, onClose }: {
  msId: number;
  membershipId: number;
  onAuthRefresh: () => void;
  onClose: () => void;
}) {
  const scope = useQuery({
    queryKey: ["member-machine-scope", msId, membershipId],
    queryFn: () => getMemberMachineScope(msId, membershipId),
    retry: false,
  });
  return <Modal open onClose={onClose} title="Machine types">
    <p className="mb-3 text-sm text-muted">A type covers all its machines, including machines added to it later. No selected types means no machines.</p>
    {scope.isPending ? <p role="status" className="text-sm text-muted">Loading machine types…</p> : null}
    {scope.error ? <p role="alert" className="text-sm text-danger">{scope.error.message}</p> : null}
    {scope.data ? <MachineTypeForm key={membershipId} msId={msId} scope={scope.data} onAuthRefresh={onAuthRefresh} onClose={onClose} /> : null}
  </Modal>;
}

function MachineTypeForm({ msId, scope, onAuthRefresh, onClose }: {
  msId: number; scope: MemberMachineScope; onAuthRefresh: () => void; onClose: () => void;
}) {
  const client = useQueryClient();
  const [draft, setDraft] = useState<number[] | null>(null);
  const ids = draft ?? scope.machine_type_ids;
  const save = useMutation({
    mutationFn: () => setMemberMachineScope(msId, scope.membership_id, ids),
    onSuccess: () => { void refreshMembershipAuthority(client, msId); onAuthRefresh(); onClose(); },
    onError: (error) => {
      if (error instanceof StructuredApiError && error.status === 409) {
        void refreshMembershipAuthority(client, msId);
        onAuthRefresh();
      }
    },
  });
  const conflict = save.error instanceof StructuredApiError && save.error.status === 409;
  if (!scope.scoping_applies) return <div className="grid gap-2"><p role="status" className="text-sm text-muted">Machine type assignment does not apply. Save the Machine Manager role first. Space Managers already cover all types.</p>{save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}</div>;
  return <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
    <fieldset disabled={save.isPending || conflict} className="grid gap-1">
      <legend className="eyebrow">Assigned machine types</legend>
      <label className="flex min-h-11 items-center gap-2 text-sm text-ink"><input type="checkbox" disabled={!scope.available_machine_types.length} checked={scope.available_machine_types.length > 0 && scope.available_machine_types.every((type) => ids.includes(type.id))} onChange={(event) => setDraft(event.target.checked ? scope.available_machine_types.map((type) => type.id) : [])} />All machine types</label>
      <p className="text-xs text-muted">The shortcut selects all currently available types. Add newly created types here later.</p>
      {scope.available_machine_types.map((type) => <label key={type.id} className="flex min-h-11 items-center gap-2 text-sm text-ink"><input type="checkbox" checked={ids.includes(type.id)} onChange={(event) => setDraft(event.target.checked ? [...ids, type.id] : ids.filter((id) => id !== type.id))} />{type.name}</label>)}
      {!scope.available_machine_types.length ? <p className="text-sm text-muted">No machine types are available.</p> : null}
    </fieldset>
    {save.error ? <p role="alert" className="text-sm text-danger">{conflict ? `Machine type assignment is no longer applicable. Assign Machine Manager first. ${save.error.message}` : save.error.message}</p> : null}
    <div className="flex justify-end gap-2"><button type="button" className="desk-button-ghost" disabled={save.isPending} onClick={onClose}>Close</button><button type="submit" className="desk-button-primary" disabled={save.isPending || conflict}>{save.isPending ? "Saving…" : "Save machine types"}</button></div>
  </form>;
}
