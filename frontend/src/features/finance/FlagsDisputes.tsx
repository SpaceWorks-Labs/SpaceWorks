import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Scale } from "lucide-react";

import { StatusPill } from "../../components/ui";
import type { Tone } from "../../components/ui/types";
import { formatMoney } from "../staff/paymentsApi";
import { NoteDialog } from "./NoteDialog";
import { financeApi, financeError, financeKeys, invalidateFinance, type CaptureFlag, type Dispute } from "./financeApi";

const FLAG_TEXT: Record<CaptureFlag["kind"], string> = {
  late: t`Paid after the charge was cancelled`, duplicate: t`Paid a second time`, mismatch: t`Paid a different amount`,
};
const DISPUTE_TONE: Record<Dispute["status"], Tone> = {
  open: "danger", under_review: "warn", won: "success", lost: "danger", closed: "neutral",
};
const DISPUTE_TEXT: Record<Dispute["status"], string> = {
  open: t`Needs response`, under_review: t`Under review`, won: t`Won`, lost: t`Lost`, closed: t`Closed`,
};

/** Online money that arrived unexpectedly. Its receipt waits for a decision; nothing is refunded here. */
export function FlagsSection({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const [done, setDone] = useState("");
  const flags = useQuery({ queryKey: financeKeys.flags(makerspaceId), queryFn: () => financeApi.flags(makerspaceId) });
  const resolve = useMutation({
    mutationFn: ({ flag, resolution, note }: { flag: CaptureFlag; resolution: string; note?: string }) =>
      financeApi.resolveFlag(makerspaceId, flag.id, { resolution, note }),
    onSuccess: () => { invalidateFinance(client, makerspaceId); setDone("Decision saved."); },
  });
  const [acknowledging, setAcknowledging] = useState<CaptureFlag | null>(null);
  const acknowledge = (flag: CaptureFlag) => setAcknowledging(flag);
  return <div className="grid min-w-0 gap-3">
    <p className="text-sm text-muted">{t`The money is already with the provider. Issue the receipt on what arrived, open a refund case for someone to approve, or note what happened.`}</p>
    {done ? <p role="status" className="text-sm">{done}</p> : null}
    {flags.error || resolve.error ? <p role="alert" className="text-sm text-danger">{financeError(flags.error ?? resolve.error)}</p> : null}
    {flags.data?.count === 0 ? <p className="text-sm text-muted">{t`No unexpected payments to decide.`}</p> : null}
    <ul className="grid gap-2">{(flags.data?.results ?? []).map(flag => <li key={flag.id} className="grid gap-2 rounded-lg border border-line bg-panel p-3">
      <p className="font-semibold">{flag.subject_label || t`Charge ${flag.payment_id}`}</p>
      <p className="text-sm">{t`${FLAG_TEXT[flag.kind]}: ${flag.captured_amount ? formatMoney(flag.captured_amount, flag.captured_currency || flag.charge_currency)
        : flag.captured_currency.toUpperCase()} received for a ${formatMoney(flag.charge_amount, flag.charge_currency)} charge (${flag.provider}).`}</p>
      <div className="flex flex-wrap gap-2">
        {flag.kind !== "duplicate" && flag.captured_amount ? <button type="button" className="desk-button" disabled={resolve.isPending}
          onClick={() => resolve.mutate({ flag, resolution: "issue_received" })}>{t`Issue receipt on what arrived`}</button> : null}
        <button type="button" className="desk-button-ghost" disabled={resolve.isPending} onClick={() => resolve.mutate({ flag, resolution: "refund_case" })}>{t`Open a refund case`}</button>
        <button type="button" className="desk-button-ghost" disabled={resolve.isPending} onClick={() => acknowledge(flag)}>{t`Note what happened`}</button>
      </div>
    </li>)}</ul>
    {acknowledging ? <NoteDialog title={t`Note what happened`} required confirmLabel={t`Save note`}
      label={t`What happened, for example where the money was refunded?`}
      onConfirm={note => { resolve.mutate({ flag: acknowledging, resolution: "acknowledged", note }); setAcknowledging(null); }}
      onClose={() => setAcknowledging(null)} /> : null}
  </div>;
}

/** Chargebacks reported by Stripe or Razorpay: a record with its status, never an action. */
export function DisputesSection({ makerspaceId }: { makerspaceId: number }) {
  const disputes = useQuery({ queryKey: financeKeys.disputes(makerspaceId), queryFn: () => financeApi.disputes(makerspaceId) });
  return <div className="grid min-w-0 gap-3">
    <p className="text-sm text-muted">{t`Respond in your provider's dashboard. A dispute never cancels a booking or ticket and never refunds by itself.`}</p>
    {disputes.error ? <p role="alert" className="text-sm text-danger">{financeError(disputes.error)}</p> : null}
    {disputes.data?.count === 0 ? <p className="text-sm text-muted">{t`No disputes.`}</p> : null}
    <ul className="grid gap-2">{(disputes.data?.results ?? []).map(row => <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-panel p-3">
      <div className="grid gap-1">
        <p className="flex items-center gap-2 font-semibold"><Scale aria-hidden="true" size={16} />{row.subject_label || t`Charge ${row.payment_id}`}</p>
        <p className="text-sm text-muted">{formatMoney(row.amount, row.currency)} · {row.provider}{row.reason ? ` · ${row.reason}` : ""}
          {row.evidence_due_at ? t` · respond by ${row.evidence_due_at.slice(0, 10)}` : ""}</p>
      </div>
      <StatusPill label={DISPUTE_TEXT[row.status]} tone={DISPUTE_TONE[row.status]} />
    </li>)}</ul>
  </div>;
}
