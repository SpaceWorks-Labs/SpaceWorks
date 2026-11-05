import { useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { EmptyState, ErrorBlock, Field, StatusPill } from '../../../components/ui';
import type { RevealRead, StaffClaimRow } from '../../../generated/api';
import { usePrizeClaims, type RevealReason } from './hackmoneyApi';
import type { Scope } from './types';

const REASONS: [RevealReason, string][] = [['pay_winner', 'To pay the winner'], ['verify_details', 'To verify the details'], ['record_tax', 'To record tax deducted']];

/** Winners' payee details and PANs (G4/G7): masked in the list; a reveal is audited and shown once, never cached. */
export function PrizeClaimsPanel({ scope }: { scope: Scope }) {
  const { list, verify, reveal } = usePrizeClaims(scope, true);
  const [shown, setShown] = useState<RevealRead | null>(null);
  const rows = list.data?.results ?? [];
  return <section className="grid gap-4" aria-label="Prize claims">
    <div className="flex items-start gap-3"><ShieldCheck className="mt-1 text-accent" aria-hidden="true" /><div>
      <h3 className="title-section">Prize claims</h3>
      <p className="text-sm text-muted">Where each winner asked to be paid. Details stay masked; revealing them is recorded in the audit log with your reason.</p></div></div>
    <ErrorBlock error={list.error || verify.error || reveal.error} />
    {shown ? <RevealBlock data={shown} onClose={() => { setShown(null); reveal.reset(); }} /> : null}
    {!list.isLoading && !rows.length ? <EmptyState title="No claims yet" description="Winners' shares and the details they give appear here." /> : null}
    {rows.map(row => <ClaimRow key={row.share_id ?? `${row.award_id}-${row.member_id}`} row={row} busy={verify.isPending || reveal.isPending}
      onVerify={() => row.share_id && verify.mutate({ shareId: row.share_id, version: row.version })}
      onReveal={reason => row.share_id && reveal.mutate({ shareId: row.share_id, version: row.version, reason }, { onSuccess: setShown })} />)}
  </section>;
}

function ClaimRow({ row, busy, onVerify, onReveal }: { row: StaffClaimRow; busy: boolean; onVerify: () => void; onReveal: (reason: RevealReason) => void }) {
  const [reason, setReason] = useState<RevealReason>('pay_winner');
  const given = row.state !== 'not_given';
  return <article className="grid gap-2 rounded-xl border border-line bg-panel p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="font-semibold">Member #{row.member_id ?? '—'} · award {row.award_id} · {row.amount}</p>
      <StatusPill label={row.verified ? 'Verified' : given ? 'Given' : 'Not given yet'} tone={row.verified ? 'success' : given ? 'warn' : 'neutral'} /></div>
    <p className="text-sm text-muted">Share {row.share_state}{given ? ` · ${row.country} ${row.method.replace('_', ' ')} · ${row.masked_details}` : ''}
      {row.pan_masked ? ` · PAN ${row.pan_masked}` : ''}</p>
    {given ? <div className="flex flex-wrap items-end gap-2">
      {!row.verified ? <button type="button" className="desk-button min-h-11" disabled={busy} onClick={onVerify}>Mark details verified</button> : null}
      <Field label="Why reveal"><select className="desk-input min-h-11" value={reason} onChange={e => setReason(e.target.value as RevealReason)}>
        {REASONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
      <button type="button" className="desk-button min-h-11" disabled={busy} onClick={() => onReveal(reason)}>Reveal to pay</button>
    </div> : null}
  </article>;
}

function RevealBlock({ data, onClose }: { data: RevealRead; onClose: () => void }) {
  return <div className="grid gap-2 rounded-xl border border-accent p-4" role="region" aria-label="Revealed payee details">
    <div className="flex items-center justify-between gap-2"><p className="font-semibold">Share {data.share_id} · {data.country} {data.method.replace('_', ' ')}</p>
      <button type="button" className="desk-button min-h-11" onClick={onClose}>Hide details</button></div>
    <dl className="grid gap-1 text-sm">{Object.entries(data.details).map(([key, value]) =>
      <div key={key} className="flex gap-2"><dt className="font-semibold">{key.replace(/_/g, ' ')}</dt><dd>{value}</dd></div>)}
      {data.pan ? <div className="flex gap-2"><dt className="font-semibold">PAN</dt><dd>{data.pan}</dd></div> : null}</dl>
  </div>;
}
