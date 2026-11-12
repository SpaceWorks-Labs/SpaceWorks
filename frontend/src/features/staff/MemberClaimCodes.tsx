import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import { Card, EmptyState, ErrorBlock, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import { LogoLoader } from "../../components/LogoLoader";
import { BoxArt } from "../../components/BoxSpinner";

export type ClaimableMember = {
  /** Null for a live guest-pass holder (0.12.0), who borrows without a membership. */
  membership_id: number | null;
  user_id: number;
  display_name: string;
  username: string;
  is_walk_in: boolean;
  is_guest_pass?: boolean;
  pass_valid_until?: string | null;
};

type ClaimCode = {
  id: number;
  membership_id: number;
  member_display_name: string;
  issued_by_id: number | null;
  issued_at: string;
  expires_at: string;
  consumed_at: string | null;
  revoked_at: string | null;
  status: "issued" | "consumed" | "revoked";
};

type IssuedClaimCode = ClaimCode & { code: string; qr_svg: string };

export function MemberClaimCodes({
  makerspaceId,
  members,
}: {
  makerspaceId: number;
  members: ClaimableMember[];
}) {
  const queryClient = useQueryClient();
  const queryKey = ["member-claim-codes", makerspaceId];
  const [membershipId, setMembershipId] = useState("");
  const [issued, setIssued] = useState<IssuedClaimCode | null>(null);
  useEffect(() => {
    setMembershipId("");
    setIssued(null);
  }, [makerspaceId]);
  const active = useQuery({
    queryKey,
    queryFn: () =>
      staffRequest<ClaimCode[]>(
        `/admin/makerspaces/${makerspaceId}/member-claim-codes`,
      ),
  });
  const issue = useMutation({
    mutationFn: () =>
      staffRequest<IssuedClaimCode>(
        `/admin/makerspaces/${makerspaceId}/member-claim-codes`,
        {
          method: "POST",
          body: JSON.stringify({ membership_id: Number(membershipId) }),
        },
      ),
    onSuccess: (claim) => {
      setIssued(claim);
      void queryClient.invalidateQueries({ queryKey });
    },
  });
  const revoke = useMutation({
    mutationFn: (claimId: number) =>
      staffRequest<ClaimCode>(
        `/admin/makerspaces/${makerspaceId}/member-claim-codes/${claimId}/revoke`,
        { method: "POST" },
      ),
    onSuccess: (claim) => {
      if (issued?.id === claim.id) setIssued(null);
      void queryClient.invalidateQueries({ queryKey });
    },
  });
  // A claim code binds a membership, so guest-pass holders (no membership) are never offered.
  const walkIns = members.filter((member): member is ClaimableMember & { membership_id: number } =>
    member.is_walk_in && member.membership_id !== null);
  const error = issue.error ?? revoke.error;

  return (
    <Card>
      <h2 className="title-section">{t`Member claim code`}</h2>
      <p className="text-sm text-muted">
        {t`Issue only while the walk-in is physically present. Hand over the code or QR; never email or text it.`}</p>
      <div className="mt-3 flex flex-col gap-2 md:flex-row">
        <select
          aria-label={t`Walk-in member`}
          className="desk-input w-full"
          value={membershipId}
          onChange={(event) => setMembershipId(event.target.value)}
        >
          <option value="">{t`Select an eligible walk-in`}</option>
          {walkIns.map((member) => (
            <option key={member.membership_id} value={member.membership_id}>
              {member.display_name || member.username}
            </option>
          ))}
        </select>
        <button
          className="desk-button-primary"
          type="button"
          disabled={!membershipId || issue.isPending}
          onClick={() => issue.mutate()}
        >
          {issue.isPending ? <><BoxArt size={16} mono />{t`Issuing…`}</> : t`Issue claim code`}
        </button>
      </div>
      {!walkIns.length ? <EmptyState message={t`No eligible walk-ins in this member list.`} /> : null}
      {issued ? (
        <div className="mt-4 grid gap-4 rounded-lg border border-line bg-surface p-4 md:grid-cols-[1fr_180px]">
          <div>
            <p className="text-sm font-semibold text-ink">{t`Hand this to ${issued.member_display_name}`}</p>
            <p className="mt-2 break-all text-lg font-semibold text-ink">{issued.code}</p>
            <p className="mt-2 text-xs text-muted">
              {t`Expires ${new Date(issued.expires_at).toLocaleString(formatLocale())}. This code will not be shown again after you leave this view.`}</p>
          </div>
          <img
            className="mx-auto aspect-square w-full max-w-64 rounded-md border border-line bg-panel p-2"
            src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(issued.qr_svg)}`}
            alt={t`Claim code QR for ${issued.member_display_name}`}
          />
        </div>
      ) : null}
      <div className="mt-4 grid gap-2">
        {active.data?.map((claim) => (
          <ListRow key={claim.id} title={claim.member_display_name}
            identity={{ kind: "avatar", name: claim.member_display_name, seed: String(claim.membership_id) }}
            meta={<span className="flex flex-wrap items-center gap-2"><StatusPill label={t`Active`} tone="success" /><span>{t`Expires `}<RelativeTime date={claim.expires_at} /></span></span>}
            right={<button className="desk-button" type="button" disabled={revoke.isPending} onClick={() => revoke.mutate(claim.id)}>{t`Revoke`}</button>} />
        ))}
        {active.isLoading ? <LogoLoader label={t`Loading active claim codes…`} size={48} className="min-h-16 py-3" /> : null}
        {active.isSuccess && !active.data?.length ? <EmptyState message={t`No active claim codes.`} /> : null}
      </div>
      {active.error ? <ErrorBlock error={active.error} resource={t`claim codes`} onRetry={() => void active.refetch()} /> : null}
      {error ? <p className="mt-3 text-sm text-danger" role="alert">{error.message}</p> : null}
    </Card>
  );
}
