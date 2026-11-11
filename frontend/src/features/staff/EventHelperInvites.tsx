import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Card, StatusBadge } from "../../components/ui";
import { useEventStaffGrantActions, useEventStaffGrants, useEventStaffInvites } from "./eventStaffGrantsApi";
import { EVENT_PERMISSIONS, type EventPermission } from "./eventStaffPermissions";
import { eventErrorText } from "./eventUi";
import {
  EventInviteLimitFields, inviteLimitError, inviteLimitFromMine, inviteLimitInput, inviteLimitText, useEventTracks, validateInviteLimit,
} from "./EventInviteLimitFields";
import type { StaffEvent } from "./eventsApiTypes";

type HelperRole = "volunteer" | "mentor" | "judge" | "sponsor_rep";

/** Mirrors the backend's HELPER_PERMISSIONS: one invitation carries one helper role's permissions. */
const HELPER_PERMISSIONS: Record<HelperRole, EventPermission[]> = {
  volunteer: ["check_in", "publish_schedule"], mentor: ["mentor_queue"], judge: ["judge"], sponsor_rep: ["view_sponsor_track"],
};

/** The helper roles a co-organizer may delegate: only what they hold, never manage_team. */
export function delegableHelperRoles(held: readonly string[]) {
  const labels: Record<HelperRole, string> = { volunteer: t`Volunteer`, mentor: t`Mentor`, judge: t`Judge`, sponsor_rep: t`Sponsor representative` };
  return (Object.keys(HELPER_PERMISSIONS) as HelperRole[])
    .map((role) => ({ role, label: labels[role], permissions: HELPER_PERMISSIONS[role].filter((p) => held.includes(p)) }))
    .filter((entry) => entry.permissions.length > 0);
}

const permissionLabel = (permission: string) => EVENT_PERMISSIONS.find(([key]) => key === permission)?.[1] ?? permission.replace(/_/g, " ");

/**
 * Decision 15: a co-organizer (manage_team, not a full manager) invites helpers within its own
 * permissions. The API lists only the rows they issued and re-checks every write.
 */
export function EventHelperInvites({ eventId, held, myLimit }: { eventId: number; held: readonly string[]; myLimit?: StaffEvent["my_limit"] }) {
  const target = { kind: "event" as const, id: eventId };
  const roles = delegableHelperRoles(held);
  const [role, setRole] = useState<HelperRole | "">(roles[0]?.role ?? "");
  const [permissions, setPermissions] = useState<EventPermission[]>(roles[0]?.permissions ?? []);
  const [email, setEmail] = useState("");
  const [sendEmail, setSendEmail] = useState(true);
  const [link, setLink] = useState("");
  // Starts from the co-organizer's own track/window (221(i)): the widest invitation they may send.
  const [limit, setLimit] = useState(() => inviteLimitFromMine(myLimit));
  const [problem, setProblem] = useState("");
  // Hackathon tracks, when the event has any and this co-organizer may read them.
  const tracks = useEventTracks(eventId).data?.results ?? [];
  const invites = useEventStaffInvites(target, 1);
  const grants = useEventStaffGrants(target, 1);
  const { invite, revoke, revokeInvite } = useEventStaffGrantActions(target);
  const pending = invite.isPending || revoke.isPending || revokeInvite.isPending;
  const error = invites.error || grants.error || invite.error || revoke.error || revokeInvite.error;
  const current = roles.find((entry) => entry.role === role);

  return <section className="grid gap-5 border-t border-line pt-5" aria-label={t`Helper invitations`}>
    <div><h3 className="title-section">{t`Helper invitations`}</h3>
      <p className="mt-1 text-sm text-muted">{t`Invite volunteers, mentors and judges with permissions you hold for this event, within your own track and time limit. Invitations expire after seven days.`}</p>
    </div>
    {roles.length === 0 ? <p className="text-sm text-muted">{t`You hold no helper permissions you can pass on.`}</p> : <Card><form className="grid gap-4" onSubmit={(event) => {
      event.preventDefault(); setLink("");
      const invalid = validateInviteLimit(limit);
      setProblem(invalid ?? "");
      if (invalid) return;
      invite.mutate({ email, send_email: sendEmail, permissions, ...(role === "volunteer" ? { role_label: "volunteer" } : {}), ...inviteLimitInput(limit) }, { onSuccess: (row) => {
        setLink(`${window.location.origin}/staff/event-invite#token=${encodeURIComponent(row.token)}`);
        invite.reset(); setEmail(""); setLimit(inviteLimitFromMine(myLimit));
      } });
    }}>
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`Invite email`}<input className="desk-input w-full min-w-0 font-normal" type="email" autoComplete="email" value={email} required disabled={pending} onChange={(event) => setEmail(event.target.value)} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`Helper role`}
        <select className="desk-input w-full min-w-0 font-normal sm:max-w-xs" value={role} disabled={pending} onChange={(event) => {
          const next = roles.find((entry) => entry.role === event.target.value);
          setRole(next?.role ?? ""); setPermissions(next?.permissions ?? []);
        }}>{roles.map((entry) => <option key={entry.role} value={entry.role}>{entry.label}</option>)}</select>
      </label>
      <fieldset disabled={pending} className="grid min-w-0 gap-x-4 sm:grid-cols-2">
        <legend className="mb-1 text-sm font-semibold text-ink">{t`Permissions`}</legend>
        {current?.permissions.map((permission) => <label key={permission} className="flex min-h-11 items-center gap-3 text-sm text-ink">
          <input type="checkbox" checked={permissions.includes(permission)} onChange={(event) => setPermissions(
            event.target.checked ? [...permissions, permission] : permissions.filter((entry) => entry !== permission))} />{permissionLabel(permission)}
        </label>)}
      </fieldset>
      <EventInviteLimitFields value={limit} onChange={(next) => { setLimit(next); setProblem(""); }} tracks={tracks} disabled={pending}
        hint={myLimit ? t`Filled in with your own track and time limit. You can narrow it, never widen it.` : undefined} />
      {problem ? <p className="text-sm text-danger" role="alert">{problem}</p> : null}
      <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={sendEmail} disabled={pending} onChange={(event) => setSendEmail(event.target.checked)} />{t`Email the invitation link`}</label>
      <div className="flex justify-end"><button className="desk-button-primary" type="submit" disabled={pending || !permissions.length}>{invite.isPending ? t`Creating invitation…` : t`Invite helper`}</button></div>
    </form></Card>}
    {link ? <div className="grid gap-3 rounded-xl border border-accent bg-accent-soft p-4" role="status">
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`Invitation link (shown once)`}<input className="desk-input code-text w-full min-w-0 font-normal" readOnly value={link} onFocus={(event) => event.target.select()} /></label>
      <button className="desk-button justify-self-start" type="button" onClick={() => setLink("")}>{t`Dismiss link`}</button>
    </div> : null}
    {error ? <p className="text-sm text-danger" role="alert">{inviteLimitError(invite.error) ?? eventErrorText(error)}</p> : null}
    <div className="grid gap-3"><h4 className="text-sm font-semibold text-ink">{t`Helpers you invited`}</h4>
      {grants.isPending ? <p className="text-sm text-muted" role="status">{t`Loading helpers…`}</p> : null}
      {grants.data?.results.length === 0 ? <p className="text-sm text-muted">{t`No helpers yet.`}</p> : null}
      {grants.data?.results.map((grant) => <article key={grant.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-panel p-4">
        <p className="min-w-0 text-sm text-ink">{t`Account #${grant.user}`}: {grant.permissions.map(permissionLabel).join(", ")}</p>
        {grant.revoked_at ? <StatusBadge status="revoked" label={t`Revoked`} />
          : <button className="desk-button-danger-outline" type="button" disabled={pending} onClick={() => revoke.mutate(grant.id)}>{t`Revoke account #${grant.user}`}</button>}
      </article>)}
    </div>
    <div className="grid gap-3"><h4 className="text-sm font-semibold text-ink">{t`Your invitations`}</h4>
      {invites.isPending ? <p className="text-sm text-muted" role="status">{t`Loading invitations…`}</p> : null}
      {invites.data?.results.length === 0 ? <p className="text-sm text-muted">{t`No invitations yet.`}</p> : null}
      {invites.data?.results.map((row) => {
        const open = !row.revoked_at && !row.redeemed_at && new Date(row.expires_at).getTime() > Date.now();
        return <article key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-panel p-4">
          <p className="min-w-0 text-sm text-ink">{t`Invitation #${row.id}`}: {row.permissions.map(permissionLabel).join(", ")}
            {inviteLimitText(row, tracks) ? <span className="block text-muted">{inviteLimitText(row, tracks)}</span> : null}</p>
          {open ? <button className="desk-button-danger-outline" type="button" disabled={pending} onClick={() => revokeInvite.mutate(row.id)}>{t`Revoke invitation #${row.id}`}</button>
            : row.revoked_at ? <StatusBadge status="revoked" label={t`Revoked`} />
            : row.redeemed_at ? <StatusBadge status="active" label={t`Accepted`} />
            : <StatusBadge status="expired" label={t`Expired`} />}
        </article>;
      })}
    </div>
  </section>;
}
