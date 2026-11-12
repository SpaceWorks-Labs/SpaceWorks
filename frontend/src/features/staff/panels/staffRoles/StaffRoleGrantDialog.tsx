import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ErrorText, Field, Modal, SegmentedControl } from "../../../../components/ui";
import { staffRequest } from "../../../../lib/api";
import { useDebouncedValue } from "../../../../lib/useDebouncedValue";
import { StaffRoleFields, validRoleSet, type RoleDraft } from "./StaffRoleEditor";
import { grantStaffRole, staffRoleErrorText, type GrantResult, type StaffRolesPolicy } from "./staffRolesApi";
import { BoxArt } from "../../../../components/BoxSpinner";
import { BoxSpinner } from "../../../../components/BoxSpinner";

type MemberOption = { id: number; user: { id: number; username: string; display_name: string } };
type Person = { id: number; name: string };

/** Grants a role set to one community member's own account, or emails an invitation they accept signed in. */
export function StaffRoleGrantDialog({ space, policy, onClose, onDone }: {
  space: number; policy: StaffRolesPolicy; onClose: () => void; onDone: (result: GrantResult, who: string) => void;
}) {
  const [mode, setMode] = useState<"member" | "email">("member");
  const [query, setQuery] = useState("");
  const [person, setPerson] = useState<Person | null>(null);
  const [email, setEmail] = useState("");
  const [draft, setDraft] = useState<RoleDraft>({ roles: [], machine_type_ids: [], machine_ids: [] });
  const search = useDebouncedValue(query.trim());
  const members = useQuery({
    queryKey: ["staff", "member-search", space, search],
    queryFn: () => staffRequest<{ results: MemberOption[] }>(`/admin/memberships?${new URLSearchParams({ makerspace_id: String(space), status: "active", q: search })}`),
    enabled: mode === "member" && search.length >= 2,
  });
  const byEmail = mode === "email" && policy.email_invites_available;
  const grant = useMutation({
    mutationFn: () => grantStaffRole(space, byEmail ? { email: email.trim(), ...draft } : { user_id: person!.id, ...draft }),
    onSuccess: result => onDone(result, byEmail ? email.trim() : person!.name),
  });
  const ready = validRoleSet(policy, draft.roles) && (byEmail ? email.trim().length > 0 : person !== null);
  const options = members.data?.results ?? [];
  return <Modal open size="xl" title={t`Add staff`} onClose={() => { if (!grant.isPending) onClose(); }}>
    <form className="grid gap-4" onSubmit={e => { e.preventDefault(); if (ready && !grant.isPending) grant.mutate(); }}>
      <fieldset disabled={grant.isPending} className="grid min-w-0 gap-4">
        <legend className="sr-only">{t`Who gets the staff roles`}</legend>
        {policy.email_invites_available ? <SegmentedControl fullWidth label={t`Add by`} value={mode}
          onChange={value => { setMode(value as "member" | "email"); grant.reset(); }}
          options={[{ value: "member", label: t`A member of this space` }, { value: "email", label: t`Invite by email` }]} /> : null}
        {byEmail ? <Field label={t`Email`} hint={t`They accept while signed in to their own account, or create one with this address.`}>
          <input className="desk-input w-full" type="email" required maxLength={254} autoComplete="off" value={email} onChange={e => setEmail(e.target.value)} />
        </Field> : <>
          <Field label={t`Find a member`} hint={t`Type at least two letters of a name or username. Staff roles are added to their own account.`}>
            <input className="desk-input w-full" type="search" value={query} onChange={e => { setQuery(e.target.value); setPerson(null); }} />
          </Field>
          {members.isFetching ? <BoxSpinner label={t`Searching…`} /> : null}
          {members.isError ? <ErrorText message={staffRoleErrorText(members.error)} /> : null}
          {search.length >= 2 && members.isSuccess && !options.length ? <p role="status" className="text-sm text-muted">{t`No active members match.`}</p> : null}
          {options.length ? <fieldset className="grid gap-2"><legend className="text-sm font-semibold text-ink">{t`Member`}</legend>
            {options.map(option => {
              const name = option.user.display_name || option.user.username;
              return <label key={option.id} className="flex min-h-11 items-center gap-3 text-sm">
                <input type="radio" name="staff-role-member" className="h-5 w-5 accent-accent" checked={person?.id === option.user.id}
                  onChange={() => setPerson({ id: option.user.id, name })} />
                <span>{name}<span className="text-muted"> · @{option.user.username}</span></span>
              </label>;
            })}
          </fieldset> : null}
        </>}
        <StaffRoleFields policy={policy} draft={draft} onChange={setDraft} />
      </fieldset>
      {grant.error ? <ErrorText message={staffRoleErrorText(grant.error)} /> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button" disabled={grant.isPending} onClick={onClose}>{t`Cancel`}</button>
        <button className="desk-button-primary" disabled={grant.isPending || !ready}>
          {grant.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : byEmail ? t`Send invitation` : t`Grant roles`}
        </button>
      </div>
    </form>
  </Modal>;
}
