import { t } from "@lingui/core/macro";
import { useMutation } from "@tanstack/react-query";
import { ErrorText, ListRow, OverflowMenu, RelativeTime, StatusPill } from "../../../../components/ui";
import {
  deliveryText, resendStaffInvitation, revokeStaffInvitation, staffRoleErrorText,
  type InvitationsPage, type StaffInvitation,
} from "./staffRolesApi";

/** Email invitations to staff roles. The accept link only ever goes to the invitee, so none is shown here. */
export function StaffRoleInvitations({ space, data, page, onPage, onChanged, onNotice }: {
  space: number; data: InvitationsPage; page: number; onPage: (page: number) => void;
  onChanged: () => void; onNotice: (text: string) => void;
}) {
  const resend = useMutation({ mutationFn: (row: StaffInvitation) => resendStaffInvitation(space, row.id),
    onSuccess: result => { onNotice(deliveryText(result.delivery_status)); onChanged(); } });
  const revoke = useMutation({ mutationFn: (row: StaffInvitation) => revokeStaffInvitation(space, row.id),
    onSuccess: result => { onNotice(`Invitation to ${result.email} revoked.`); onChanged(); } });
  const pending = resend.isPending || revoke.isPending;
  const error = resend.error ?? revoke.error;
  return <div className="grid gap-3">
    {error ? <ErrorText message={staffRoleErrorText(error)} /> : null}
    {data.results.map(row => {
      const open = !row.accepted_at && !row.revoked_at;
      return <ListRow key={row.id} title={row.email} identity={{ kind: "avatar", name: row.email, seed: `invite-${row.id}` }}
        meta={<>{row.role_name}{open ? <> {t` · Expires `}<RelativeTime date={row.expires_at} /></> : null}</>}
        right={<div className="flex flex-wrap items-center gap-2">
          <StatusPill label={invitationState(row)} tone={row.accepted_at ? "success" : open && !isExpired(row) ? "accent" : "neutral"} />
          {open ? <>
            <button type="button" className="desk-button min-h-11" disabled={pending} onClick={() => resend.mutate(row)}>{t`Resend`}</button>
            <OverflowMenu label={t`Actions for ${row.email}`} actions={[{ label: t`Revoke`, tone: "danger", disabled: pending,
              disabledReason: pending ? "Wait for the current invitation update." : undefined,
              confirm: { title: t`Revoke invitation?`, message: t`The invitation sent to ${row.email} stops working. Send a new one if they still need access.`, confirmLabel: t`Revoke` },
              onClick: () => revoke.mutate(row) }]} />
          </> : null}
        </div>} />;
    })}
    {data.previous || data.next ? <div className="flex items-center gap-3">
      <button type="button" className="desk-button min-h-11" disabled={!data.previous} onClick={() => onPage(page - 1)}>{t`Previous`}</button>
      <span className="text-sm text-muted">{t`Page ${page}`}</span>
      <button type="button" className="desk-button min-h-11" disabled={!data.next} onClick={() => onPage(page + 1)}>{t`Next`}</button>
    </div> : null}
  </div>;
}

function isExpired(row: StaffInvitation) {
  return !row.accepted_at && !row.revoked_at && new Date(row.expires_at).getTime() < Date.now();
}
function invitationState(row: StaffInvitation) {
  return row.accepted_at ? "Accepted" : row.revoked_at ? "Revoked" : isExpired(row) ? "Expired" : "Waiting";
}
