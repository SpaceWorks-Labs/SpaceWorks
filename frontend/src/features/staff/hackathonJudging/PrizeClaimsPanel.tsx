import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { sentenceCase } from '../../../lib/sentenceCase';
import { ShieldCheck } from 'lucide-react';
import { EmptyState, ErrorBlock, Field, StatusPill } from '../../../components/ui';
import type { RevealRead, StaffClaimRow } from '../../../generated/api';
import { usePrizeClaims, usePrizePool, type RevealReason } from './hackmoneyApi';
import { shareStateLabel } from './prizeLabels';
import { formatMoney, paymentMethodLabel } from '../../../lib/money';
import type { Scope } from './types';

const reasons = (): [RevealReason, string][] => [['pay_winner', t`To pay the winner`], ['verify_details', t`To verify the details`], ['record_tax', t`To record tax deducted`]];
const methodLabel = (method: string) => paymentMethodLabel(method);
const detailLabel = (key: string) => ({ upi_id: t`UPI ID`, account_number: t`Account number`, account_holder: t`Account holder`, account_name: t`Account name`, ifsc: t`IFSC`, bank_name: t`Bank name`, iban: t`IBAN`, swift: t`SWIFT`, routing_number: t`Routing number`, phone: t`Phone`, email: t`Email`, address: t`Address` } as Record<string, string>)[key] ?? sentenceCase(key);

/** Winners' payee details and PANs (G4/G7): masked in the list; a reveal is audited and shown once, never cached. */
export function PrizeClaimsPanel({ scope }: { scope: Scope }) {
  const { list, verify, reveal } = usePrizeClaims(scope, true);
  const [shown, setShown] = useState<RevealRead | null>(null);
  const rows = list.data?.results ?? [];
  const currency = usePrizePool(scope, true).data?.currency ?? '';
  return <section className="grid gap-4" aria-label={t`Prize claims`}>
    <div className="flex items-start gap-3"><ShieldCheck className="mt-1 text-accent-ink" aria-hidden="true" /><div>
      <h3 className="title-section">{t`Prize claims`}</h3>
      <p className="text-sm text-muted">{t`Where each winner asked to be paid. Details stay masked; revealing them is recorded in the audit log with your reason.`}</p></div></div>
    <ErrorBlock error={list.error || verify.error || reveal.error} />
    {shown ? <RevealBlock data={shown} onClose={() => { setShown(null); reveal.reset(); }} /> : null}
    {!list.isLoading && !rows.length ? <EmptyState title={t`No claims yet`} description={t`Winners' shares and the details they give appear here.`} /> : null}
    {rows.map(row => <ClaimRow key={row.share_id ?? `${row.award_id}-${row.member_id}`} row={row} currency={currency} busy={verify.isPending || reveal.isPending}
      onVerify={() => row.share_id && verify.mutate({ shareId: row.share_id, version: row.version })}
      onReveal={reason => row.share_id && reveal.mutate({ shareId: row.share_id, version: row.version, reason }, { onSuccess: setShown })} />)}
  </section>;
}

function ClaimRow({ row, currency, busy, onVerify, onReveal }: { row: StaffClaimRow; currency: string; busy: boolean; onVerify: () => void; onReveal: (reason: RevealReason) => void }) {
  const [reason, setReason] = useState<RevealReason>('pay_winner');
  const given = row.state !== 'not_given';
  return <article className="grid gap-2 rounded-xl border border-line bg-panel p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="font-semibold">{t`Member #${row.member_id ?? '—'} · award ${row.award_id} · ${formatMoney(row.amount, currency)}`}</p>
      <StatusPill label={row.verified ? t`Verified` : given ? t`Given` : t`Not given yet`} tone={row.verified ? 'success' : given ? 'warn' : 'neutral'} /></div>
    <p className="text-sm text-muted">{t`Share ${shareStateLabel(row.share_state)}${given ? ` · ${row.country} ${methodLabel(row.method)} · ${row.masked_details}` : ''}`}
      {row.pan_masked ? t` · PAN ${row.pan_masked}` : ''}</p>
    {given ? <div className="flex flex-wrap items-end gap-2">
      {!row.verified ? <button type="button" className="desk-button min-h-11" disabled={busy} onClick={onVerify}>{t`Mark details verified`}</button> : null}
      <Field label={t`Why reveal`}><select className="desk-input min-h-11" value={reason} onChange={e => setReason(e.target.value as RevealReason)}>
        {reasons().map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
      <button type="button" className="desk-button min-h-11" disabled={busy} onClick={() => onReveal(reason)}>{t`Reveal to pay`}</button>
    </div> : null}
  </article>;
}

function RevealBlock({ data, onClose }: { data: RevealRead; onClose: () => void }) {
  return <div className="grid gap-2 rounded-xl border border-accent p-4" role="region" aria-label={t`Revealed payee details`}>
    <div className="flex items-center justify-between gap-2"><p className="font-semibold">{t`Share ${data.share_id} · ${data.country} ${methodLabel(data.method)}`}</p>
      <button type="button" className="desk-button min-h-11" onClick={onClose}>{t`Hide details`}</button></div>
    <dl className="grid gap-1 text-sm">{Object.entries(data.details).map(([key, value]) =>
      <div key={key} className="flex gap-2"><dt className="font-semibold">{detailLabel(key)}</dt><dd>{value}</dd></div>)}
      {data.pan ? <div className="flex gap-2"><dt className="font-semibold">{t`PAN`}</dt><dd>{data.pan}</dd></div> : null}</dl>
  </div>;
}
