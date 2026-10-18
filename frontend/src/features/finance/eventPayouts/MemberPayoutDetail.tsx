import { DetailLayout } from "../../../components/layouts";
import { useMemberPayout } from "./api";
import { money, scopeIdentity } from "./format";
import { PayeeCollection } from "./PayeeCollection";
import { PayeeReveal } from "./PayeeReveal";
import { PayoutHistory } from "./PayoutHistory";
import { collectedPayee, permits } from "./types";

export function MemberPayoutDetail({ actorId, id }: { actorId: number; id: string }) {
  const query = useMemberPayout(actorId, id);
  const row = query.data;
  const payee = collectedPayee(row?.payee);
  return <DetailLayout title={row?.event_title ?? "Your reimbursement"} status={row?.state}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "Your reimbursement could not be loaded.", onRetry: () => { void query.refetch(); } }}
    main={row ? <div key={`${scopeIdentity(actorId)}:${id}:${row.version}`} className="grid gap-6">
      <p>{money(row.approved_minor, row.currency)} approved · {money(row.effective_paid_minor, row.currency)} recorded paid · {money(row.remaining_minor, row.currency)} remaining</p>
      <p>Eligibility: {row.eligibility_status.replace(/_/g, " ")}</p>
      {payee ? <p>{payee.masked_details} · {payee.verified ? "Routing verified" : "Routing awaiting review"}</p> : null}
      {permits(row, "submit_payee") || permits(row, "delete_payee") ? <PayeeCollection actorId={actorId} payout={row} />
        : <p>Payment routing is not currently requested.</p>}
      <PayeeReveal actorId={actorId} obligationId={id} version={row.version} allowed={permits(row, "reveal_payee")} />
      <PayoutHistory entries={row.entries} />
    </div> : null} />;
}
