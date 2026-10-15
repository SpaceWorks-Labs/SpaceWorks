import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EmptyState, ListRow, OverflowMenu, RelativeTime, StatusPill } from "../../../components/ui";

import { staffRequest } from "../../../lib/api";
import type { StaffRole } from "./rolesApi";

type Invitation = { id: number; email: string; role_name: string; expires_at: string; accepted_at: string | null; revoked_at: string | null };
type Delivery = { accept_url: string; delivery_status: string };
type Page = { results: Invitation[]; next: string | null; previous: string | null; count: number };

export function StaffInvitations({ msId, roles }: { msId: number; roles: StaffRole[] }) {
  const client = useQueryClient();
  const [email, setEmail] = useState("");
  const [roleId, setRoleId] = useState("");
  const [delivery, setDelivery] = useState<Delivery>();
  const [page, setPage] = useState(1);
  const base = `/admin/makerspaces/${msId}/staff-invitations`;
  const key = ["staff", "invitations", msId];
  const list = useQuery({ queryKey: [...key, page], queryFn: () => staffRequest<Page>(`${base}?page=${page}`) });
  const create = useMutation({ mutationFn: () => staffRequest<Delivery>(base, { method: "POST", body: JSON.stringify({ email, role_id: Number(roleId), expires_in_days: 7 }) }),
    onSuccess: (data) => { setDelivery(data); setEmail(""); void client.invalidateQueries({ queryKey: key }); } });
  const update = useMutation({ mutationFn: ({ id, action }: { id: number; action: "revoke" | "resend" }) => staffRequest<Partial<Delivery>>(`${base}/${id}/${action}`, { method: "POST" }),
    onSuccess: (data) => { setDelivery(data.accept_url ? data as Delivery : undefined); void client.invalidateQueries({ queryKey: key }); } });
  const staffRoles = roles.filter((role) => role.granted_actions.length > 0);
  return <section className="grid gap-4 rounded border border-line p-4">
    <h2 className="text-lg font-semibold">Staff invitations</h2>
    <form className="flex flex-wrap items-end gap-3" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}>
      <label className="grid min-w-0 flex-1 basis-56 gap-1">Email<input className="desk-input w-full" type="email" value={email} required onChange={(event) => setEmail(event.target.value)} /></label>
      <label className="grid min-w-0 flex-1 basis-48 gap-1">Role<select className="desk-input w-full" value={roleId} required onChange={(event) => setRoleId(event.target.value)}>
        <option value="">Choose a role</option>{staffRoles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
      </select></label>
      <button className="desk-button-primary" disabled={create.isPending || !staffRoles.length}>Invite staff</button>
    </form>
    {delivery ? <div role="status"><p>Delivery: {delivery.delivery_status}. You can also share this link privately:</p>
      <input className="desk-input w-full" aria-label="Invitation link" readOnly value={delivery.accept_url} onFocus={(event) => event.currentTarget.select()} />
      <button className="desk-button mt-3" type="button" onClick={() => void navigator.clipboard.writeText(delivery.accept_url)}>Copy link</button>
    </div> : null}
    {list.error || create.error || update.error ? <p role="alert" className="text-danger">{(list.error ?? create.error ?? update.error)?.message}</p> : null}
    {list.isLoading ? <p>Loading invitations…</p> : null}
    {list.data && !list.data.results.length ? <EmptyState message="No staff invitations yet. Invite someone to share the work." /> : null}
    <div className="grid gap-3">{list.data?.results.map(row => <ListRow key={row.id} title={row.email}
      identity={{ kind: "avatar", name: row.email, seed: row.email }} meta={<>{row.role_name}{row.accepted_at || row.revoked_at ? null : <> · Expires <RelativeTime date={row.expires_at} /></>}</>}
      right={<div className="flex flex-wrap items-center gap-3"><StatusPill label={invitationState(row)} tone={row.accepted_at ? "success" : row.revoked_at || isExpired(row) ? "neutral" : "accent"} />
      {!row.accepted_at && !row.revoked_at ? <><button className="desk-button" disabled={update.isPending} onClick={() => update.mutate({ id: row.id, action: "resend" })}>Resend</button>
        <OverflowMenu label={`Actions for ${row.email}`} actions={[{ label: "Revoke", tone: "danger", disabled: update.isPending, disabledReason: update.isPending ? "Wait for the current invitation update." : undefined, confirm: { title: "Revoke invitation?", message: `The link sent to ${row.email} stops working. Send a new invitation if they still need access.`, confirmLabel: "Revoke" }, onClick: () => update.mutate({ id: row.id, action: "revoke" }) }]} /></> : null}</div>} />)}</div>
    <div className="flex flex-wrap gap-3"><button className="desk-button" disabled={!list.data?.previous} onClick={() => setPage(page - 1)}>Previous</button><button className="desk-button" disabled={!list.data?.next} onClick={() => setPage(page + 1)}>Next</button></div>
  </section>;
}

function isExpired(row: Invitation) {
  return !row.accepted_at && !row.revoked_at && new Date(row.expires_at).getTime() < Date.now();
}
function invitationState(row: Invitation) {
  return row.accepted_at ? "Accepted" : row.revoked_at ? "Revoked" : isExpired(row) ? "Expired" : "Unused";
}
