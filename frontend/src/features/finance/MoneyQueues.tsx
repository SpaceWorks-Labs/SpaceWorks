import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { StatusPill } from "../../components/ui";
import { formatMoney } from "../staff/paymentsApi";
import { NoteDialog } from "./NoteDialog";
import { financeApi, financeError, financeKeys, invalidateFinance, words, type Claim, type Confirmation } from "./financeApi";

/**
 * Offline income waiting on staff: payers' "I've paid" claims, and settlements a colleague
 * recorded that need a second person (two-person check). Confirming writes the receipt.
 */
export function MoneyQueues({ makerspaceId, claimsOn }: { makerspaceId: number; claimsOn: boolean }) {
  const client = useQueryClient();
  const [message, setMessage] = useState("");
  const claims = useQuery({ queryKey: financeKeys.claims(makerspaceId, "submitted"),
    queryFn: () => financeApi.claims(makerspaceId, "submitted"), enabled: claimsOn });
  const confirmations = useQuery({ queryKey: financeKeys.confirmations(makerspaceId),
    queryFn: () => financeApi.confirmations(makerspaceId) });
  const decideClaim = useMutation({
    mutationFn: ({ row, decision, note }: { row: Claim; decision: "confirm" | "reject"; note?: string }) =>
      financeApi.decideClaim(makerspaceId, row.id, decision, note),
    onSuccess: (row) => { invalidateFinance(client, makerspaceId);
      setMessage(row.status === "awaiting_confirmation" ? "Recorded. A second person now confirms it." : `Claim ${row.status}.`); },
  });
  const decideRow = useMutation({
    mutationFn: ({ row, decision, note }: { row: Confirmation; decision: "confirm" | "reject"; note?: string }) =>
      financeApi.decideConfirmation(makerspaceId, row.id, decision, note),
    onSuccess: (row) => { invalidateFinance(client, makerspaceId); setMessage(`Settlement ${row.status}.`); },
  });
  const [rejecting, setRejecting] = useState<((note: string) => void) | null>(null);
  const reject = (apply: (note: string) => void) => setRejecting(() => apply);
  const error = decideClaim.error ?? decideRow.error;
  return <div className="grid min-w-0 gap-6">
    {message ? <p role="status" className="text-sm">{message}</p> : null}
    {error ? <p role="alert" className="text-sm text-danger">{financeError(error)}</p> : null}
    {claimsOn ? <section className="grid gap-2" aria-labelledby="claims-heading">
      <h3 id="claims-heading" className="title-section">Payers say they paid</h3>
      <p className="text-sm text-muted">Check the transfer reached your account before confirming. Confirming records the receipt.</p>
      {claims.data?.count === 0 ? <p className="text-sm text-muted">No claims waiting.</p> : null}
      <ul className="grid gap-2">{(claims.data?.results ?? []).map(row => <li key={row.id} className="grid gap-2 rounded-lg border border-line bg-panel p-3">
        <p className="font-semibold">{row.subject_label || `Charge ${row.payment_id}`} · {formatMoney(row.amount, row.currency)}</p>
        <p className="text-sm text-muted">{words(row.method)} reference <span className="font-mono">{row.reference}</span>, paid {row.paid_on}
          {row.via_pay_link ? " · through a pay link" : ""}</p>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="desk-button" disabled={decideClaim.isPending} onClick={() => decideClaim.mutate({ row, decision: "confirm" })}>Confirm payment</button>
          <button type="button" className="desk-button-ghost" disabled={decideClaim.isPending} onClick={() => reject(note => decideClaim.mutate({ row, decision: "reject", note }))}>Not received</button>
        </div>
      </li>)}</ul>
    </section> : null}
    <section className="grid gap-2" aria-labelledby="checker-heading">
      <h3 id="checker-heading" className="title-section">Waiting for a second person</h3>
      <p className="text-sm text-muted">The person who recorded a settlement can't confirm it themselves.</p>
      {confirmations.error ? <p role="alert" className="text-sm text-danger">{financeError(confirmations.error)}</p> : null}
      {confirmations.data?.count === 0 ? <p className="text-sm text-muted">Nothing waiting.</p> : null}
      <ul className="grid gap-2">{(confirmations.data?.results ?? []).map(row => <li key={row.id} className="grid gap-2 rounded-lg border border-line bg-panel p-3">
        <p className="font-semibold">{row.subject_label || `Charge ${row.payment_id}`} · {formatMoney(row.amount, row.currency)}</p>
        <p className="text-sm text-muted">{words(row.method)}{row.reference ? ` · ${row.reference}` : ""} · received {row.received_at.slice(0, 10)}</p>
        {row.proposed_by_me ? <StatusPill label="You recorded this" tone="info" /> : <div className="flex flex-wrap gap-2">
          <button type="button" className="desk-button" disabled={decideRow.isPending} onClick={() => decideRow.mutate({ row, decision: "confirm" })}>Confirm</button>
          <button type="button" className="desk-button-ghost" disabled={decideRow.isPending} onClick={() => reject(note => decideRow.mutate({ row, decision: "reject", note }))}>Reject</button>
        </div>}
      </li>)}</ul>
    </section>
    {rejecting ? <NoteDialog title="Reject" label="Tell the payer why (optional)" confirmLabel="Reject"
      onConfirm={note => { rejecting(note); setRejecting(null); }} onClose={() => setRejecting(null)} /> : null}
  </div>;
}
