import { t } from "@lingui/core/macro";
import { payoutStateLabel } from "./labels";
import { useState } from "react";
import { DetailLayout } from "../../../components/layouts";
import { usePayout } from "./api";
import { PayeeReveal } from "./PayeeReveal";
import { PayeeReview } from "./PayeeReview";
import { PayoutRecording } from "./PayoutRecording";
import { PayoutHolds } from "./PayoutHolds";
import { PayoutHistory } from "./PayoutHistory";
import { CancelObligation } from "./CancelObligation";
import { ReceiptViewer } from "./ReceiptViewer";
import { DecisionHistory } from "./DecisionHistory";
import { money, scopeIdentity } from "./format";
import { collectedPayee, permits } from "./types";
import type { FinanceScope, PayoutDetail as Detail, PayoutEntry } from "./types";

export function PayoutDetail({ scope, id, poolVersion }: { scope: FinanceScope; id: string; poolVersion?: number; canRecord?: boolean }) {
  const query = usePayout(scope, id);
  const row = query.data;
  return <DetailLayout title={row?.event_title ?? t`Payout obligation`} state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready",
    error: t`This obligation could not be loaded.`, onRetry: () => { void query.refetch(); } }}
    status={row ? payoutStateLabel(row.state) : undefined} main={row ? <DetailContent key={`${scopeIdentity(scope.actorId, scope.makerspaceId)}:${id}:${row.version}:${row.allowed_actions?.join()}`}
      scope={scope} row={row} poolVersion={row.expected_pool_version ?? poolVersion} /> : null} />;
}
function DetailContent({ scope, row, poolVersion }: { scope: FinanceScope; row: Detail; poolVersion?: number }) {
  const [correction, setCorrection] = useState<PayoutEntry | undefined>();
  const payee = collectedPayee(row.payee);
  return <div className="grid gap-6">
    <p>{t`${money(row.approved_minor, row.currency)} approved · ${money(row.effective_paid_minor, row.currency)} recorded paid · ${money(row.remaining_minor, row.currency)} remaining`}</p>
    <p>{payee ? t`Payee: ${payee.masked_details}` : t`Payee: Details not collected`}</p>
    <PayeeReveal scope={scope} obligationId={row.id} version={row.version} allowed={permits(row, "reveal_payee")} />
    <PayeeReview scope={scope} payout={row} />
    <PayoutHolds scope={scope} payout={row} />
    {row.attachments ? <section className="grid gap-3" aria-label={t`Finance receipts`}><h2 className="font-semibold">{t`Finance receipts`}</h2>
      {row.attachments.length ? row.attachments.map(receipt => <ReceiptViewer key={receipt.id} scope={scope} receipt={receipt} />) : <p>{t`No receipts are bound to this obligation.`}</p>}</section>
      : <p className="text-sm text-muted">{t`Receipt metadata is unavailable.`}</p>}
    {row.revisions ? <DecisionHistory revisions={row.revisions} currency={row.currency} /> : null}
    <PayoutHistory entries={row.entries} onAmend={permits(row, "amend") ? setCorrection : undefined} />
    {permits(row, "record") ? <PayoutRecording scope={scope} payout={row} /> : null}
    {correction && permits(row, "amend") && permits(row.entries.find(entry => entry.id === correction.id), "amend") ? <section className="grid gap-3" aria-label={t`Selected recording correction`}>
      <PayoutRecording key={correction.id} scope={scope} payout={row} amends={correction} />
      <button className="desk-button min-h-11" type="button" onClick={() => setCorrection(undefined)}>{t`Close correction form`}</button>
    </section> : null}
    <CancelObligation scope={scope} payout={row} poolVersion={poolVersion} />
  </div>;
}
