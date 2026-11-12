import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import {
  declineInvitationRequest,
  inviteFromRequest,
  listInvitationRequests,
  membershipPlanKeys,
  planErrorText,
  type InvitationRequest,
} from "./membershipPlansApi";
import { Panel } from "./panels/shared";
import { LogoLoader } from "../../components/LogoLoader";

type Role = { id: number; name: string };

const STATUS_ORDER: Record<InvitationRequest["status"], number> = { pending: 0, invited: 1, declined: 2 };

/** Pending first, then newest first inside each status -- staff work the open queue. */
export function sortInvitationRequests(rows: InvitationRequest[]) {
  return [...rows].sort((a, b) =>
    STATUS_ORDER[a.status] - STATUS_ORDER[b.status] || b.created_at.localeCompare(a.created_at));
}

export function InvitationRequestsSection({ makerspaceId, roles }: { makerspaceId: number; roles: Role[] }) {
  const client = useQueryClient();
  const requests = useQuery({
    queryKey: membershipPlanKeys.invitationRequests(makerspaceId),
    queryFn: () => listInvitationRequests(makerspaceId),
  });
  const [roleByRequest, setRoleByRequest] = useState<Record<number, number>>({});
  const refresh = () => {
    client.invalidateQueries({ queryKey: membershipPlanKeys.invitationRequests(makerspaceId) });
    // "Invite" creates an ordinary membership invitation, which the requests panel lists.
    client.invalidateQueries({ queryKey: ["members", makerspaceId] });
  };
  const invite = useMutation({
    mutationFn: ({ id, roleId }: { id: number; roleId: number }) => inviteFromRequest(id, roleId),
    onSuccess: refresh,
  });
  const decline = useMutation({ mutationFn: (id: number) => declineInvitationRequest(id), onSuccess: refresh });
  const error = invite.error ?? decline.error;
  const rows = sortInvitationRequests(requests.data ?? []);
  const pendingCount = rows.filter((row) => row.status === "pending").length;

  return (
    <Panel title={t`Invitation requests`}>
      <p className="mb-3 text-sm text-muted">
        {t`People who asked to be invited from the public page. Inviting sends the same membership invitation a manager types by hand.${pendingCount ? ` ${pendingCount} pending.` : ""}`}
      </p>
      {requests.isLoading ? <LogoLoader label={t`Loading invitation requests…`} size={48} className="min-h-16 py-3" /> : null}
      {requests.isError ? <p className="text-sm text-danger" role="alert">{planErrorText(requests.error, "Could not load invitation requests.")}</p> : null}
      {requests.data?.length === 0 ? <EmptyState message={t`No invitation requests yet. New requests appear here.`} /> : null}
      {rows.map((row) => {
        const roleId = roleByRequest[row.id] ?? roles[0]?.id ?? null;
        return (
          <ListRow key={row.id} title={row.name || row.email} identity={{ kind: "avatar", name: row.name || row.email, seed: row.email }}
            meta={<>
                <span className="[overflow-wrap:anywhere]">{row.email}</span>{row.phone ? ` · ${row.phone}` : ""} · <RelativeTime date={row.created_at} />
              {row.message ? <span className="mt-1 block whitespace-pre-wrap">{row.message}</span> : null}
            </>}
            right={<div className="flex flex-wrap items-center gap-2">
              <StatusPill tone={row.status === "pending" ? "warn" : row.status === "invited" ? "success" : "neutral"} label={row.status} />
              {row.status === "pending" ? (
                <>
                  <select
                    aria-label={t`Role for ${row.name || row.email}`}
                    className="desk-input"
                    value={roleId ?? ""}
                    onChange={(event) => setRoleByRequest((current) => ({ ...current, [row.id]: Number(event.target.value) }))}
                  >
                    {roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
                  </select>
                  <button
                    className="desk-button-primary"
                    type="button"
                    disabled={!roleId || invite.isPending}
                    onClick={() => roleId && invite.mutate({ id: row.id, roleId })}
                  >
                    {t`Invite`}</button>
                  <button className="desk-button" type="button" disabled={decline.isPending} onClick={() => decline.mutate(row.id)}>
                    {t`Decline`}</button>
                </>
              ) : null}
            </div>} />
        );
      })}
      {error ? <p className="mt-2 text-sm text-danger" role="alert">{planErrorText(error, "Could not update the request.")}</p> : null}
    </Panel>
  );
}
