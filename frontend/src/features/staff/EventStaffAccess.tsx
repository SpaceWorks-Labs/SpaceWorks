import { useState } from "react";

import { Skeleton } from "../../components/ui";
import { EventPermissionFields } from "./EventPermissionFields";
import { useEventStaffGrantActions, useEventStaffGrants, useEventStaffInvites, type EventStaffGrant, type StaffGrantTarget } from "./eventStaffGrantsApi";
import type { EventPermission } from "./eventStaffPermissions";
import { eventErrorText } from "./eventUi";

export function EventStaffAccess({ target }: { target: StaffGrantTarget }) {
  const [email, setEmail] = useState("");
  const [sendEmail, setSendEmail] = useState(true);
  const [permissions, setPermissions] = useState<EventPermission[]>([]);
  const [grantPage, setGrantPage] = useState(1);
  const [invitePage, setInvitePage] = useState(1);
  const [link, setLink] = useState("");
  const [editing, setEditing] = useState<EventStaffGrant | null>(null);
  const grants = useEventStaffGrants(target, grantPage);
  const invites = useEventStaffInvites(target, invitePage);
  const { invite, update, revoke, revokeInvite } = useEventStaffGrantActions(target);
  const pending = invite.isPending || update.isPending || revoke.isPending || revokeInvite.isPending;
  const error = grants.error || invites.error || invite.error || update.error || revoke.error || revokeInvite.error;

  return <section className="grid gap-4 border-t border-line pt-5" aria-label="Staff access">
    <div><h3 className="title-section">Staff access</h3>
      <p className="text-sm text-muted">Delegate selected operations for this {target.kind}. Invitations expire after seven days. Recipients need a matching verified email.</p>
    </div>
    <form className="grid gap-3 rounded-lg border border-line p-3" onSubmit={(event) => {
      event.preventDefault(); setLink("");
      invite.mutate({ email, send_email: sendEmail, permissions }, { onSuccess: (row) => {
        setLink(`${window.location.origin}/staff/event-invite#token=${encodeURIComponent(row.token)}`);
        // The raw token stays in this component's state, never in a query cache.
        invite.reset(); setEmail(""); setPermissions([]);
      } });
    }}>
      <label className="grid gap-1 text-sm font-semibold">Invite email<input className="desk-input" type="email" autoComplete="email" value={email} required disabled={pending} onChange={(event) => setEmail(event.target.value)} /></label>
      <EventPermissionFields value={permissions} onChange={setPermissions} disabled={pending} />
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={sendEmail} disabled={pending} onChange={(event) => setSendEmail(event.target.checked)} />Email the invitation link</label>
      <button className="desk-button-primary justify-self-start" type="submit" disabled={pending || !permissions.length}>{invite.isPending ? "Creating invitation..." : "Invite staff"}</button>
    </form>
    {link ? <div className="grid gap-2" role="status"><label className="grid gap-1 text-sm">Invitation link (shown once)<input className="desk-input" readOnly value={link} onFocus={(event) => event.target.select()} /></label><button className="desk-button justify-self-start" type="button" onClick={() => setLink("")}>Dismiss link</button></div> : null}
    {grants.isLoading || invites.isLoading ? <Skeleton className="h-24 w-full" /> : null}
    {error ? <p className="text-sm text-danger" role="alert">{eventErrorText(error)}</p> : null}
    <div><h4 className="font-semibold text-ink">Granted staff</h4>
      {grants.data?.results.length === 0 ? <p className="mt-2 text-sm text-muted">No staff grants yet.</p> : null}
      {grants.data?.results.map((grant) => <article key={grant.id} className="mt-2 grid gap-2 rounded-lg border border-line p-3">
        <p className="text-sm font-semibold">Account #{grant.user}{grant.revoked_at ? " · Revoked" : ""}</p>
        {editing?.id === grant.id ? <form className="grid gap-2" onSubmit={(event) => {
          event.preventDefault(); update.mutate({ id: grant.id, permissions: editing.permissions }, { onSuccess: () => setEditing(null) });
        }}><EventPermissionFields legend={`Permissions for account #${grant.user}`} value={editing.permissions} disabled={pending} onChange={(next) => setEditing({ ...editing, permissions: next })} />
          <div className="flex gap-2"><button className="desk-button-primary" disabled={pending || !editing.permissions.length}>Save permissions</button><button className="desk-button" type="button" onClick={() => setEditing(null)}>Cancel</button></div>
        </form> : <p className="text-sm text-muted">{grant.permissions.map((entry) => entry.replace(/_/g, " ")).join(", ")}</p>}
        {!grant.revoked_at ? <div className="flex gap-2"><button className="desk-button" type="button" disabled={pending} onClick={() => setEditing({ ...grant })}>Edit account #{grant.user}</button><button className="desk-button-danger" type="button" disabled={pending} onClick={() => revoke.mutate(grant.id)}>Revoke account #{grant.user}</button></div> : null}
      </article>)}
      <PageControls page={grantPage} previous={grants.data?.previous} next={grants.data?.next} onPage={setGrantPage} label="Staff grants" />
    </div>
    <div><h4 className="font-semibold text-ink">Invitations</h4>
      {invites.data?.results.length === 0 ? <p className="mt-2 text-sm text-muted">No invitations yet.</p> : null}
      {invites.data?.results.map((row) => {
        const state = row.revoked_at ? "Revoked" : row.redeemed_at ? "Redeemed" : new Date(row.expires_at).getTime() <= Date.now() ? "Expired" : "Pending";
        return <article key={row.id} className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line p-3 text-sm">
          <div>Invitation #{row.id} · {state}<p className="text-muted">Expires {new Date(row.expires_at).toLocaleString()}</p></div>
          {state === "Pending" ? <button className="desk-button-danger" type="button" disabled={pending} onClick={() => revokeInvite.mutate(row.id)}>Revoke invitation #{row.id}</button> : null}
        </article>;
      })}
      <PageControls page={invitePage} previous={invites.data?.previous} next={invites.data?.next} onPage={setInvitePage} label="Invitations" />
    </div>
  </section>;
}

function PageControls({ page, previous, next, onPage, label }: {
  page: number; previous?: string | null; next?: string | null; onPage: (page: number) => void; label: string;
}) {
  return <div className="mt-2 flex items-center gap-3 text-sm" aria-label={`${label} pagination`}>
    <button className="desk-button" type="button" disabled={!previous} onClick={() => onPage(Math.max(1, page - 1))}>Previous</button>
    <span>Page {page}</span><button className="desk-button" type="button" disabled={!next} onClick={() => onPage(page + 1)}>Next</button>
  </div>;
}
