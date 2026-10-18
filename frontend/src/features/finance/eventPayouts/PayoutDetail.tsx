import { useState } from "react";
import { DetailLayout } from "../../../components/layouts";
import { usePayout, usePayoutCommand } from "./api";
import { PayeeReveal } from "./PayeeReveal";
import { PayoutRecording } from "./PayoutRecording";
import { CancelObligation } from "./CancelObligation";
import type { FinanceScope, PayoutEntry } from "./types";

export function PayoutDetail({ scope, id, canRecord, poolVersion }: { scope: FinanceScope; id: string; canRecord: boolean; poolVersion?: number }) {
  const query = usePayout(scope, id);
  const [correction, setCorrection] = useState<PayoutEntry | undefined>();
  const verify = usePayoutCommand(scope, id, "payee/verify");
  const row = query.data;
  return <DetailLayout title={row?.event_title ?? "Payout obligation"} state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "This obligation could not be loaded." }}
    status={row?.state} main={row ? <div className="grid gap-6">
      <p>{row.currency} {row.approved_minor} minor units approved · {row.effective_paid_minor} recorded paid · {row.remaining_minor} remaining</p>
      <p>Eligibility: {row.eligibility_status.replace(/_/g, " ")}</p>
      <p>Payee: {row.payee?.masked_details ?? "Details not collected"}</p>
      <PayeeReveal key={`${row.id}:${row.version}`} scope={scope} obligationId={row.id} version={row.version} />
      {row.payee?.id && !row.payee.verified ? <button type="button" className="desk-button min-h-11" disabled={verify.isPending} onClick={() => verify.mutate({
        expected_version: row.version, expected_payee_version: row.payee.version, payee_revision_id: row.payee.id,
      })}>Confirm inspected routing details</button> : null}
      {verify.error ? <p role="alert">Verification failed. Reload and confirm your recent authentication.</p> : null}
      <section aria-label="Payout history" className="grid gap-3"><h2 className="font-semibold">Payout history</h2>
        {row.entries.map(entry => <article className="rounded-2xl border border-line p-4" key={entry.id}>
          <p>{entry.is_void ? "Voided recording" : `${entry.currency} ${entry.amount_minor} minor units`} · {entry.method} · {entry.reference}</p>
          <p>{entry.amends_id ? `Corrects record ${entry.amends_id}` : "Original record"}</p>
          {canRecord && !row.entries.some(item => item.amends_id === entry.id) ? <button className="desk-button min-h-11" type="button" onClick={() => setCorrection(entry)}>Correct recording error</button> : null}
        </article>)}</section>
      {canRecord && row.state === "open" && row.eligibility_status === "eligible" && row.payee?.verified ? <PayoutRecording scope={scope} payout={row} /> : null}
      {canRecord && correction ? <PayoutRecording key={correction.id} scope={scope} payout={row} amends={correction} /> : null}
      <CancelObligation scope={scope} payout={row} poolVersion={poolVersion} />
    </div> : null} />;
}
