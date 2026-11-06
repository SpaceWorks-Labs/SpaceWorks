import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  approveDisclosure,
  getDisclosureClosure,
  listDisclosureApprovals,
  revokeDisclosure,
  tenantMigrationKeys,
} from "./tenantMigrationApi";
import { ActionControl } from "../../components/ui";
import { ErrorText, StatusPill } from "./tenantMigrationUi";

export function TenantMigrationDisclosure({ makerspaceId, active = true }: { makerspaceId: number; active?: boolean }) {
  const client = useQueryClient();
  const [review, setReview] = useState<{ digest: string; decisions: Record<number, boolean>; acknowledged: boolean }>({
    digest: "", decisions: {}, acknowledged: false,
  });
  const closure = useQuery({
    queryKey: tenantMigrationKeys.closure(makerspaceId),
    queryFn: () => getDisclosureClosure(makerspaceId),
  });
  const approvals = useQuery({
    queryKey: tenantMigrationKeys.approvals(makerspaceId),
    queryFn: () => listDisclosureApprovals(makerspaceId),
  });
  const approve = useMutation({
    mutationFn: () => approveDisclosure(makerspaceId, {
      digest: closure.data!.digest,
      decisions: closure.data!.identities.map((identity) => ({
        user_id: identity.id,
        approved: decisions[identity.id] ?? false,
      })),
    }),
    onSuccess: () => client.invalidateQueries({ queryKey: tenantMigrationKeys.approvals(makerspaceId) }),
  });
  const revoke = useMutation({
    mutationFn: (approvalId: string) => revokeDisclosure(makerspaceId, approvalId),
    onSuccess: () => client.invalidateQueries({ queryKey: tenantMigrationKeys.approvals(makerspaceId) }),
  });
  const activeApproval = approvals.data?.find(
    (item) => !item.revoked_at && item.closure_digest === closure.data?.digest,
  );
  const voidApprovals = approvals.data?.filter(
    (item) => !item.revoked_at && item.closure_digest !== closure.data?.digest,
  ) ?? [];
  const reviewMatches = review.digest === closure.data?.digest;
  const decisions = reviewMatches ? review.decisions : {};
  const acknowledged = reviewMatches && review.acknowledged;

  if (!active) return null;
  return (
    <section aria-labelledby="migration-disclosure-title" className="min-w-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow">{t`Safety gate`}</p>
          <h3 className="title-section" id="migration-disclosure-title">{t`Disclosure closure review`}</h3>
        </div>
        {activeApproval ? <StatusPill tone="success">{t`APPROVED`}</StatusPill> : <StatusPill tone="warn">{t`REVIEW REQUIRED`}</StatusPill>}
      </div>
      <p className="mt-2 text-sm text-ink">
        {t`The selected people’s email, name, and phone will be disclosed to the target deployment. Review every identity and decide whether it may travel in this exact export closure.`}</p>

      {closure.isLoading || approvals.isLoading ? <p className="mt-3 text-sm text-muted">{t`Computing the exact identity closure…`}</p> : null}
      <ErrorText error={closure.error ?? approvals.error} />
      {voidApprovals.map((approval) => (
        <div className="mt-3 rounded-md border border-danger-line bg-panel p-3" key={approval.id} role="status">
          <p className="font-semibold text-danger">{t`VOID — disclosure closure changed after approval`}</p>
          <p className="mt-1 text-xs text-muted">{t`Previously approved digest: `}<span className="code-text break-all">{approval.closure_digest}</span></p>
        </div>
      ))}

      {closure.data ? (
        <>
          <p className="mt-3 text-xs text-muted">{t`Exact closure digest`}</p>
          <p className="break-all code-text text-xs text-ink" data-testid="closure-digest">{closure.data.digest}</p>
          <div className="mt-3 grid gap-2">
            {closure.data.identities.length === 0 ? <p className="text-sm text-muted">{t`This closure contains no identities.`}</p> : null}
            {closure.data.identities.map((identity) => (
              <label className="flex min-h-11 items-start gap-3 rounded-md border border-line bg-surface p-3" key={identity.id}>
                <input
                  className="mt-1 h-5 w-5 accent-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                  type="checkbox"
                  checked={decisions[identity.id] ?? false}
                  disabled={Boolean(activeApproval)}
                  onChange={(event) => setReview((current) => ({
                    digest: closure.data!.digest,
                    acknowledged: current.digest === closure.data!.digest && current.acknowledged,
                    decisions: {
                      ...(current.digest === closure.data!.digest ? current.decisions : {}),
                      [identity.id]: event.target.checked,
                    },
                  }))}
                />
                <span className="min-w-0 text-sm text-ink">
                  <span className="block font-semibold">{identity.display_name || identity.username}</span>
                  <span className="block break-words text-muted">{identity.email || t`No email`} · {identity.phone || t`No phone`}</span>
                  <span className="block text-xs text-muted">{t`${identity.first_name} ${identity.last_name} · @${identity.username} · user ${identity.id}`}</span>
                  <span className="block text-xs text-muted">{t`Joined ${new Date(identity.date_joined).toLocaleString(formatLocale())}`}</span>
                  <span className="mt-1 block text-xs font-semibold">{decisions[identity.id] ? t`Disclose this identity` : t`Withhold this identity`}</span>
                </span>
              </label>
            ))}
          </div>
          {activeApproval ? (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <p className="text-sm text-success-ink">{t`${activeApproval.approved_count} of ${activeApproval.identity_count} identities approved for this digest.`}</p>
              <ActionControl action={{ label: t`Revoke approval`, tone: "danger", pending: revoke.isPending, pendingLabel: "Revoking…",
                confirm: { title: t`Revoke approval?`, message: t`Exports can no longer be created from this closure until it is reviewed and approved again.`, confirmLabel: t`Revoke approval` },
                onClick: () => revoke.mutate(activeApproval.id) }} />
            </div>
          ) : (
            <div className="mt-3">
              <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
                <input className="h-5 w-5 accent-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" type="checkbox" checked={acknowledged} onChange={(event) => setReview((current) => ({
                  digest: closure.data!.digest,
                  acknowledged: event.target.checked,
                  decisions: current.digest === closure.data!.digest ? current.decisions : {},
                }))} />
                {t`I reviewed every person and understand the approved fields leave this deployment.`}</label>
              <button className="desk-button-primary mt-2" type="button" disabled={!acknowledged || approve.isPending} onClick={() => approve.mutate()}>
                {approve.isPending ? t`Approving exact closure…` : t`Approve exact closure`}
              </button>
            </div>
          )}
          <ErrorText error={approve.error} field="digest" />
          <ErrorText error={revoke.error} />
        </>
      ) : null}
    </section>
  );
}
