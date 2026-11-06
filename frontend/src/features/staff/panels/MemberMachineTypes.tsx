import { t } from "@lingui/core/macro";
import { useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Callout, ErrorText, Modal, Skeleton } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { getMemberMachineScope, setMemberMachineScope, type MemberMachineScope } from "./rolesApi";
import { refreshMembershipAuthority } from "./roleSets";

const card = "flex min-h-11 cursor-pointer items-start gap-3 rounded-xl border border-line bg-panel p-3 has-checked:border-accent has-checked:bg-accent-soft has-focus-visible:ring-2 has-focus-visible:ring-focus has-disabled:cursor-not-allowed has-disabled:opacity-60";
const box = "mt-0.5 h-5 w-5 shrink-0 accent-accent";

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
  return <Modal open onClose={onClose} title={t`Machine types`}>
    <div className="grid gap-4">
      <p className="text-sm text-muted">{t`A type covers all its machines, including machines added to it later. No selected types means no machines.`}</p>
      {scope.isPending ? <div role="status" aria-label={t`Loading machine types`}><Skeleton className="h-24 w-full" /></div> : null}
      {scope.error ? <ErrorText message={scope.error.message} /> : null}
      {scope.data ? <MachineTypeForm key={membershipId} msId={msId} scope={scope.data} onAuthRefresh={onAuthRefresh} onClose={onClose} /> : null}
    </div>
  </Modal>;
}

function MachineTypeForm({ msId, scope, onAuthRefresh, onClose }: {
  msId: number; scope: MemberMachineScope; onAuthRefresh: () => void; onClose: () => void;
}) {
  const id = useId();
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
  const types = scope.available_machine_types;
  if (!scope.scoping_applies) return <div className="grid gap-2"><Callout size="inline" tone="warn" lead="Machine type assignment does not apply." body={t`Save the Machine Manager role first. Space Managers already cover all types.`} />{save.error ? <ErrorText message={save.error.message} /> : null}</div>;
  return <form className="grid gap-4" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
    <fieldset disabled={save.isPending || conflict} className="grid min-w-0 gap-2">
      <legend className="text-sm font-semibold text-ink">{t`Assigned machine types`}</legend>
      <label className={card}>
        <input className={box} type="checkbox" disabled={!types.length} aria-describedby={`${id}-all`}
          checked={types.length > 0 && types.every((type) => ids.includes(type.id))}
          onChange={(event) => setDraft(event.target.checked ? types.map((type) => type.id) : [])} />
        <span className="font-semibold text-ink">{t`All machine types`}</span>
      </label>
      <p id={`${id}-all`} className="text-xs text-muted">{t`The shortcut selects all currently available types. Add newly created types here later.`}</p>
      {!ids.length && types.length ? <p className="text-sm text-danger">{t`Nothing selected: this person can manage no machines.`}</p> : null}
      <div className="@container"><div className="grid gap-2 @md:grid-cols-2">
        {types.map((type) => <label key={type.id} className={card}>
          <input className={box} type="checkbox" aria-labelledby={`${id}-${type.id}`} aria-describedby={`${id}-${type.id}-kind`} checked={ids.includes(type.id)}
            onChange={(event) => setDraft(event.target.checked ? [...ids, type.id] : ids.filter((typeId) => typeId !== type.id))} />
          <span className="grid min-w-0 gap-1">
            <span id={`${id}-${type.id}`} className="font-semibold text-ink">{type.name}</span>
            <span id={`${id}-${type.id}-kind`} className="text-xs text-muted">{type.is_global ? t`Built-in` : t`This makerspace`}</span>
          </span>
        </label>)}
      </div></div>
      {!types.length ? <p className="text-sm text-muted">{t`No machine types are available.`}</p> : null}
    </fieldset>
    {save.error ? <ErrorText message={conflict ? t`Machine type assignment is no longer applicable. Assign Machine Manager first. ${save.error.message}` : save.error.message} /> : null}
    <div className="desk-actions flex flex-wrap justify-end gap-2">
      <button type="button" className="desk-button-ghost" disabled={save.isPending} onClick={onClose}>{t`Close`}</button>
      <button type="submit" className="desk-button-primary" disabled={save.isPending || conflict}>{save.isPending ? t`Saving…` : t`Save machine types`}</button>
    </div>
  </form>;
}
