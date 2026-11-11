import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, ErrorBlock, Skeleton } from "../../../components/ui";
import { NoteDialog } from "../../finance/NoteDialog";
import { MAKER_CHECKER_NOTICE } from "../PaymentReconcileActions";
import { formatMoney, invalidatePaymentViews, settlementMethodLabel } from "../paymentsApi";
import { areaErrorText, areaKeys, areaPaymentsApi, type AreaClaim } from "./areaPaymentsApi";

/**
 * Decision 242(b): members' "I paid" claims on the caller's own-area charges. Confirming writes the
 * receipt (or, with the two-person check on, proposes it for a second `record_payment` holder);
 * "Not received" rejects the claim with an optional note to the payer.
 */
export function AreaClaimsList({ makerspaceId, area }: { makerspaceId: number; area?: string }) {
  const client = useQueryClient();
  const [message, setMessage] = useState("");
  const [rejecting, setRejecting] = useState<AreaClaim | null>(null);
  const claims = useQuery({ queryKey: areaKeys.claims(makerspaceId, area), queryFn: () => areaPaymentsApi.claims(makerspaceId, area) });
  const decide = useMutation({
    mutationFn: ({ claim, note }: { claim: AreaClaim; note?: string }) => note === undefined
      ? areaPaymentsApi.confirmClaim(makerspaceId, claim.id) : areaPaymentsApi.rejectClaim(makerspaceId, claim.id, note),
    onSuccess: (row) => {
      invalidatePaymentViews(client, makerspaceId);
      setMessage(row.status === "awaiting_confirmation" ? MAKER_CHECKER_NOTICE
        : row.status === "rejected" ? t`Marked as not received. The payer has been told.` : t`Payment confirmed and the receipt recorded.`);
    },
    onError: () => { setMessage(""); void claims.refetch(); },
  });
  if (claims.isLoading) return <div role="status" aria-label={t`Loading claims`}><Skeleton className="h-24 w-full" /></div>;
  if (claims.error) return <ErrorBlock error={claims.error} resource={t`payment claims`} onRetry={() => { void claims.refetch(); }} />;
  // Every claim on a charge the caller owns, in any of their areas (the server narrows the rows).
  const rows = claims.data?.results ?? [];
  return <section aria-labelledby="area-claims-heading" className="grid gap-3">
    <div className="grid gap-1">
      <h3 id="area-claims-heading" className="title-section">{t`People who say they paid`}</h3>
      <p className="text-sm text-muted">{t`Check the money reached your account before confirming. Confirming records the receipt. While a claim is open, online payment is paused for that member.`}</p>
    </div>
    {message ? <p role="status" className="text-sm text-ink">{message}</p> : null}
    {decide.error ? <p role="alert" className="text-sm text-danger">{areaErrorText(decide.error)}</p> : null}
    {!rows.length ? <EmptyState message={t`No one is waiting. Claims show up here when a payer tells you they paid.`} /> : null}
    <ul className="grid gap-2">{rows.map(claim => <li key={claim.id} className="grid gap-2 rounded-xl border border-line bg-panel p-3">
      <p className="font-semibold text-ink [overflow-wrap:anywhere]">{claim.subject_label || t`Charge ${claim.payment_id}`}
        {" · "}<span className="tabular-nums">{formatMoney(claim.amount, claim.currency)}</span></p>
      <p className="text-sm text-muted [overflow-wrap:anywhere]">{t`${settlementMethodLabel(claim.method)} reference`}{" "}
        <span className="code-text">{claim.reference}</span>{t`, paid ${claim.paid_on}`}{claim.via_pay_link ? t` · through a pay link` : ""}</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button" disabled={decide.isPending} onClick={() => decide.mutate({ claim })}>{t`Confirm payment`}</button>
        <button type="button" className="desk-button-ghost" disabled={decide.isPending} onClick={() => setRejecting(claim)}>{t`Not received`}</button>
      </div>
    </li>)}</ul>
    {rejecting ? <NoteDialog title={t`Not received`} label={t`Tell the payer why (optional)`} confirmLabel={t`Mark not received`}
      onClose={() => setRejecting(null)} onConfirm={note => { decide.mutate({ claim: rejecting, note }); setRejecting(null); }} /> : null}
  </section>;
}
