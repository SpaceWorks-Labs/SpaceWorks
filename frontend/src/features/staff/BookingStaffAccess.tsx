import { useState } from "react";

import { ErrorText, Field, SettingsSection, Skeleton, StatusPill } from "../../components/ui";
import { BookingPermissionFields } from "./BookingPermissionFields";
import { useBookingStaffGrantActions, useBookingStaffGrants, useBookingStaffInvites, type BookingStaffGrant, type StaffGrantTarget } from "./bookingStaffGrantsApi";
import type { BookingPermission } from "./bookingStaffPermissions";
import { eventErrorText } from "./eventUi";

export function BookingStaffAccess({ target }: { target: StaffGrantTarget }) {
  const [email, setEmail] = useState("");
  const [sendEmail, setSendEmail] = useState(true);
  const [permissions, setPermissions] = useState<BookingPermission[]>([]);
  const [grantPage, setGrantPage] = useState(1);
  const [invitePage, setInvitePage] = useState(1);
  const [link, setLink] = useState("");
  const [editing, setEditing] = useState<BookingStaffGrant | null>(null);
  const grants = useBookingStaffGrants(target, grantPage);
  const invites = useBookingStaffInvites(target, invitePage);
  const { invite, update, revoke, revokeInvite } = useBookingStaffGrantActions(target);
  const pending = invite.isPending || update.isPending || revoke.isPending || revokeInvite.isPending;
  const error = grants.error || invites.error || invite.error || update.error || revoke.error || revokeInvite.error;

  return <SettingsSection title="Staff access" description="Delegate selected operations for this resource. Invitations expire after seven days. Recipients need a matching verified email.">
    <form className="grid gap-4 py-5" aria-label="Invite resource staff" onSubmit={(event) => {
      event.preventDefault(); setLink("");
      invite.mutate({ email, send_email: sendEmail, permissions }, { onSuccess: (row) => {
        setLink(`${window.location.origin}/staff/booking-invite#token=${encodeURIComponent(row.token)}`);
        // The raw token stays in this component's state, never in a query cache.
        invite.reset(); setEmail(""); setPermissions([]);
      } });
    }}>
      <Field label="Invite email"><input className="desk-input w-full" type="email" autoComplete="email" value={email} required disabled={pending} onChange={(event) => setEmail(event.target.value)} /></Field>
      <BookingPermissionFields value={permissions} onChange={setPermissions} disabled={pending} />
      <label className="flex min-h-11 items-center gap-2 text-sm text-ink"><input type="checkbox" checked={sendEmail} disabled={pending} onChange={(event) => setSendEmail(event.target.checked)} />Email the invitation link</label>
      <button className="desk-button-primary justify-self-start" type="submit" disabled={pending || !permissions.length}>{invite.isPending ? "Creating invitation..." : "Invite staff"}</button>
    </form>
    {link ? <div className="grid gap-3 py-5" role="status">
      <Field label="Invitation link (shown once)"><input className="desk-input code-text w-full min-w-0 text-xs" readOnly value={link} onFocus={(event) => event.target.select()} /></Field>
      <button className="desk-button justify-self-start" type="button" onClick={() => setLink("")}>Dismiss link</button>
    </div> : null}
    {grants.isLoading || invites.isLoading ? <div className="py-5"><Skeleton className="h-24 w-full" /></div> : null}
    {error ? <div className="py-5"><ErrorText message={eventErrorText(error)} /></div> : null}
    <div className="py-5"><h3 className="title-section">Granted staff</h3>
      {grants.data?.results.length === 0 ? <p className="mt-2 text-sm text-muted">No staff grants yet.</p> : null}
      <ul className="mt-2 divide-y divide-line">{grants.data?.results.map((grant) => <li key={grant.id} className="grid gap-3 py-4">
        <div className="flex flex-wrap items-center gap-2"><p className="text-sm font-semibold text-ink">Account #{grant.user}</p>{grant.revoked_at ? <StatusPill label="Revoked" tone="neutral" /> : null}</div>
        {editing?.id === grant.id ? <form className="grid gap-3" onSubmit={(event) => {
          event.preventDefault(); update.mutate({ id: grant.id, permissions: editing.permissions }, { onSuccess: () => setEditing(null) });
        }}><BookingPermissionFields legend={`Permissions for account #${grant.user}`} value={editing.permissions} disabled={pending} onChange={(next) => setEditing({ ...editing, permissions: next })} />
          <div className="flex flex-wrap gap-2"><button className="desk-button-primary" disabled={pending || !editing.permissions.length}>Save permissions</button><button className="desk-button" type="button" onClick={() => setEditing(null)}>Cancel</button></div>
        </form> : <p className="text-sm text-muted">{grant.permissions.map((entry) => entry.replace(/_/g, " ")).join(", ")}</p>}
        {!grant.revoked_at ? <div className="flex flex-wrap gap-2"><button className="desk-button" type="button" disabled={pending} onClick={() => setEditing({ ...grant })}>Edit account #{grant.user}</button><button className="desk-button-danger-outline" type="button" disabled={pending} onClick={() => revoke.mutate(grant.id)}>Revoke account #{grant.user}</button></div> : null}
      </li>)}</ul>
      <PageControls page={grantPage} previous={grants.data?.previous} next={grants.data?.next} onPage={setGrantPage} label="Staff grants" />
    </div>
    <div className="py-5"><h3 className="title-section">Invitations</h3>
      {invites.data?.results.length === 0 ? <p className="mt-2 text-sm text-muted">No invitations yet.</p> : null}
      <ul className="mt-2 divide-y divide-line">{invites.data?.results.map((row) => {
        const state = row.revoked_at ? "Revoked" : row.redeemed_at ? "Redeemed" : new Date(row.expires_at).getTime() <= Date.now() ? "Expired" : "Pending";
        return <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 py-4 text-sm">
          <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="font-semibold text-ink">Invitation #{row.id}</p>
            <StatusPill label={state} tone={state === "Pending" ? "warn" : state === "Redeemed" ? "success" : "neutral"} /></div>
            <p className="mt-1 text-muted">Expires {new Date(row.expires_at).toLocaleString()}</p></div>
          {state === "Pending" ? <button className="desk-button-danger-outline" type="button" disabled={pending} onClick={() => revokeInvite.mutate(row.id)}>Revoke invitation #{row.id}</button> : null}
        </li>;
      })}</ul>
      <PageControls page={invitePage} previous={invites.data?.previous} next={invites.data?.next} onPage={setInvitePage} label="Invitations" />
    </div>
  </SettingsSection>;
}

function PageControls({ page, previous, next, onPage, label }: {
  page: number; previous?: string | null; next?: string | null; onPage: (page: number) => void; label: string;
}) {
  if (!previous && !next) return null;
  return <nav className="mt-3 flex flex-wrap items-center justify-end gap-2 text-sm text-muted" aria-label={`${label} pagination`}>
    <button className="desk-button" type="button" disabled={!previous} onClick={() => onPage(Math.max(1, page - 1))}>Previous</button>
    <span>Page {page}</span><button className="desk-button" type="button" disabled={!next} onClick={() => onPage(page + 1)}>Next</button>
  </nav>;
}
