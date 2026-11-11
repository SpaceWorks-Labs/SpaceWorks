import { t } from "@lingui/core/macro";
import { payoutEligibilityLabel, payoutStateLabel } from "./labels";
import { DetailLayout } from "../../../components/layouts";
import { useMemberPayout } from "./api";
import { money, scopeIdentity } from "./format";
import { PayeeCollection } from "./PayeeCollection";
import { PayeeFilesSection } from "./PayeeFiles";
import { PayeeReveal } from "./PayeeReveal";
import { PayoutHistory } from "./PayoutHistory";
import { collectedPayee, permits } from "./types";

export function MemberPayoutDetail({ actorId, id }: { actorId: number; id: string }) {
  const query = useMemberPayout(actorId, id);
  const row = query.data;
  const payee = collectedPayee(row?.payee);
  return <DetailLayout title={row?.event_title ?? t`Your reimbursement`} status={row ? payoutStateLabel(row.state) : undefined}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: t`Your reimbursement could not be loaded.`, onRetry: () => { void query.refetch(); } }}
    main={row ? <div className="grid gap-6"><div key={`${scopeIdentity(actorId)}:${id}:${row.version}`} className="grid gap-6">
      <p>{t`${money(row.approved_minor, row.currency)} approved · ${money(row.effective_paid_minor, row.currency)} recorded paid · ${money(row.remaining_minor, row.currency)} remaining`}</p>
      <p>{t`Eligibility: ${payoutEligibilityLabel(row.eligibility_status)}`}</p>
      {payee ? <p>{payee.masked_details} · {payee.verified ? t`Routing verified` : t`Routing awaiting review`}</p> : null}
      {permits(row, "submit_payee") || permits(row, "delete_payee") ? <PayeeCollection actorId={actorId} payout={row} />
        : <p>{t`Payment routing is not currently requested.`}</p>}
      <PayeeReveal actorId={actorId} obligationId={id} version={row.version} allowed={permits(row, "reveal_payee")} />
      <PayoutHistory entries={row.entries} />
    </div>
      {/* Outside the version-keyed block: each file command bumps the obligation version, and the
          files uploaded in this window must survive that refetch. Keyed by the owner and payee revision. */}
      <PayeeFilesSection key={`${scopeIdentity(actorId)}:${id}`} actorId={actorId} payout={row} />
    </div> : null} />;
}
