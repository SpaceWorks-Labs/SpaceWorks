import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { eventPermissionLabel } from "./eventStaffPermissions";
import { useState } from "react";

import { Card, Skeleton, StatusBadge } from "../../components/ui";
import { EventPermissionFields, RoleLabelField, roleLabelText, type RoleLabel } from "./EventPermissionFields";
import { useEventStaffGrantActions, useEventStaffGrants, useEventStaffInvites, type EventStaffGrant, type StaffGrantTarget } from "./eventStaffGrantsApi";
import type { EventPermission } from "./eventStaffPermissions";
import { eventErrorText } from "./eventUi";
import { EventInviteLimitFields, emptyInviteLimit, inviteLimitInput, inviteLimitText, useEventTracks, validateInviteLimit } from "./EventInviteLimitFields";
import { EventPanelPager } from "./EventPanelPager";

const permissionList = (permissions: string[]) => permissions.map(eventPermissionLabel).join(", ");
const rowCard = "grid min-w-0 gap-3 rounded-2xl border border-line bg-panel p-4";

export function EventStaffAccess({ target }: { target: StaffGrantTarget }) {
  const [email, setEmail] = useState("");
  const [sendEmail, setSendEmail] = useState(true);
  const [permissions, setPermissions] = useState<EventPermission[]>([]);
  const [role, setRole] = useState<RoleLabel>("");
  const [grantPage, setGrantPage] = useState(1);
  const [invitePage, setInvitePage] = useState(1);
  const [link, setLink] = useState("");
  const [editing, setEditing] = useState<EventStaffGrant | null>(null);
  const [limit, setLimit] = useState(emptyInviteLimit);
  const [problem, setProblem] = useState("");
  const tracks = useEventTracks(target.id, target.kind === "event").data?.results ?? [];
  const grants = useEventStaffGrants(target, grantPage);
  const invites = useEventStaffInvites(target, invitePage);
  const { invite, update, revoke, revokeInvite } = useEventStaffGrantActions(target);
  const pending = invite.isPending || update.isPending || revoke.isPending || revokeInvite.isPending;
  const error = grants.error || invites.error || invite.error || update.error || revoke.error || revokeInvite.error;

  return <section className="grid gap-5 border-t border-line pt-5" aria-label={t`Staff access`}>
    <div><h3 className="title-section">{t`Staff access`}</h3>
      <p className="mt-1 text-sm text-muted">{t`Delegate selected operations for this ${target.kind}. Invitations expire after seven days. Recipients need a matching verified email.`}</p>
    </div>
    <Card><form className="grid gap-4" onSubmit={(event) => {
      event.preventDefault(); setLink("");
      const invalid = validateInviteLimit(limit);
      setProblem(invalid ?? "");
      if (invalid) return;
      invite.mutate({ email, send_email: sendEmail, permissions, ...(role ? { role_label: role } : {}), ...inviteLimitInput(limit) }, { onSuccess: (row) => {
        setLink(`${window.location.origin}/staff/event-invite#token=${encodeURIComponent(row.token)}`);
        // The raw token stays in this component's state, never in a query cache.
        invite.reset(); setEmail(""); setPermissions([]); setRole(""); setLimit(emptyInviteLimit);
      } });
    }}>
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`Invite email`}<input className="desk-input w-full min-w-0 font-normal" type="email" autoComplete="email" value={email} required disabled={pending} onChange={(event) => setEmail(event.target.value)} /></label>
      <EventPermissionFields value={permissions} onChange={setPermissions} disabled={pending}
        onSpeakerPreset={() => { setPermissions(["check_in"]); setRole("speaker"); }} />
      <RoleLabelField value={role} onChange={setRole} disabled={pending} />
      <EventInviteLimitFields value={limit} onChange={(next) => { setLimit(next); setProblem(""); }} tracks={tracks} disabled={pending}
        hint={t`Leave these empty for access to every track at any time.`} />
      {problem ? <p className="text-sm text-danger" role="alert">{problem}</p> : null}
      <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={sendEmail} disabled={pending} onChange={(event) => setSendEmail(event.target.checked)} />{t`Email the invitation link`}</label>
      <div className="flex justify-end"><button className="desk-button-primary" type="submit" disabled={pending || !permissions.length}>{invite.isPending ? t`Creating invitation…` : t`Invite staff`}</button></div>
    </form></Card>
    {link ? <div className="grid gap-3 rounded-xl border border-accent bg-accent-soft p-4" role="status">
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`Invitation link (shown once)`}<input className="desk-input code-text w-full min-w-0 font-normal" readOnly value={link} onFocus={(event) => event.target.select()} /></label>
      <button className="desk-button justify-self-start" type="button" onClick={() => setLink("")}>{t`Dismiss link`}</button>
    </div> : null}
    {grants.isLoading || invites.isLoading ? <Skeleton className="h-24 w-full" /> : null}
    {error ? <p className="text-sm text-danger" role="alert">{eventErrorText(error)}</p> : null}
    <div className="grid gap-3"><h4 className="text-sm font-semibold text-ink">{t`Granted staff`}</h4>
      {grants.data?.results.length === 0 ? <p className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">{t`No staff grants yet.`}</p> : null}
      {grants.data?.results.map((grant) => <article key={grant.id} className={`${rowCard} ${grant.revoked_at ? "border-dashed bg-surface" : ""}`}>
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <p className="title-section min-w-0 flex-1 break-words">{t`Account #${grant.user}`}</p>
          {roleLabelText(grant.role_label) ? <span className="rounded-full border border-info px-2 py-0.5 text-xs font-semibold text-info-ink">{roleLabelText(grant.role_label)}</span> : null}
          {grant.revoked_at ? <StatusBadge status="revoked" label={t`Revoked`} /> : null}
        </div>
        {editing?.id === grant.id ? <form className="grid gap-3" onSubmit={(event) => {
          event.preventDefault(); update.mutate({ id: grant.id, permissions: editing.permissions, role_label: editing.role_label ?? "" }, { onSuccess: () => setEditing(null) });
        }}><EventPermissionFields legend={t`Permissions for account #${grant.user}`} value={editing.permissions} disabled={pending} onChange={(next) => setEditing({ ...editing, permissions: next })} />
          <RoleLabelField label={t`Role label for account #${grant.user}`} value={editing.role_label ?? ""} disabled={pending} onChange={(next) => setEditing({ ...editing, role_label: next })} />
          <div className="flex flex-wrap gap-2"><button className="desk-button-primary" type="submit" disabled={pending || !editing.permissions.length}>{t`Save permissions`}</button><button className="desk-button" type="button" onClick={() => setEditing(null)}>{t`Cancel`}</button></div>
        </form> : <p className="text-sm text-muted">{permissionList(grant.permissions)}</p>}
        {!grant.revoked_at ? <div className="flex flex-wrap gap-2"><button className="desk-button" type="button" disabled={pending} onClick={() => setEditing({ ...grant })}>{t`Edit account #${grant.user}`}</button><button className="desk-button-danger-outline" type="button" disabled={pending} onClick={() => revoke.mutate(grant.id)}>{t`Revoke account #${grant.user}`}</button></div> : null}
      </article>)}
      <EventPanelPager page={grantPage} setPage={setGrantPage} count={grants.data?.count} next={grants.data?.next} />
    </div>
    <div className="grid gap-3"><h4 className="text-sm font-semibold text-ink">{t`Invitations`}</h4>
      {invites.data?.results.length === 0 ? <p className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">{t`No invitations yet.`}</p> : null}
      {invites.data?.results.map((row) => {
        const state = row.revoked_at ? "Revoked" : row.redeemed_at ? "Redeemed" : new Date(row.expires_at).getTime() <= Date.now() ? "Expired" : "Pending";
        return <article key={row.id} className={`${rowCard} sm:flex sm:flex-wrap sm:items-center sm:justify-between`}>
          <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="title-section">{t`Invitation #${row.id}`}</p><StatusBadge status={state.toLowerCase()} label={({ Pending: t`Pending`, Redeemed: t`Redeemed`, Revoked: t`Revoked`, Expired: t`Expired` } as Record<string, string>)[state] ?? state} /></div>
            <p className="mt-1 text-sm text-muted">{t`Expires ${new Date(row.expires_at).toLocaleString(formatLocale())}`}</p>
            {inviteLimitText(row, tracks) ? <p className="text-sm text-muted">{inviteLimitText(row, tracks)}</p> : null}</div>
          {state === "Pending" ? <button className="desk-button-danger-outline justify-self-start" type="button" disabled={pending} onClick={() => revokeInvite.mutate(row.id)}>{t`Revoke invitation #${row.id}`}</button> : null}
        </article>;
      })}
      <EventPanelPager page={invitePage} setPage={setInvitePage} count={invites.data?.count} next={invites.data?.next} />
    </div>
  </section>;
}
