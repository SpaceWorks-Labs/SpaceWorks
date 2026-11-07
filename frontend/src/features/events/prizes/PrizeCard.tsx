import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { StatusPill } from '../../../components/ui';
import { KIND_LABELS, STATUS_LABELS, payoutRow, statusTone, type MyPrize, type PrizeCommand } from './api';
import { PrizeClaimForm } from './PrizeClaimForm';
import { PrizeSplitEditor } from './PrizeSplitEditor';

type Mode = 'idle' | 'split' | 'claim';

function when(value: string | null) {
  return value ? new Date(value).toLocaleString(formatLocale(), { dateStyle: 'medium', timeStyle: 'short' }) : '';
}

/** One award in "My prizes": status, my share, my payout (gross, tax, net) and my masked claim. */
export function PrizeCard({ prize, makerspaceId, actorId, pending, send }: {
  prize: MyPrize; makerspaceId: number; actorId: number; pending: boolean;
  send: (command: PrizeCommand, done?: () => void) => void;
}) {
  const [mode, setMode] = useState<Mode>('idle');
  const can = (action: string) => prize.allowed_actions.includes(action);
  const share = prize.my_share; const claim = prize.claim; const payout = payoutRow(prize.my_payout);
  const run = (suffix: string, version: number, fields?: Record<string, unknown>) =>
    send({ eventId: prize.event_id, suffix, version, fields }, () => setMode('idle'));
  const deadline = prize.claim_deadline ? new Date(prize.claim_deadline) : null;
  return <article className="grid gap-3 rounded-xl border border-line bg-panel p-4" aria-label={`${prize.prize_name}, ${prize.event_title}`}>
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div><p className="font-semibold">{t`${prize.prize_name} · rank ${prize.rank}`}</p>
        <p className="text-sm text-muted">{prize.event_title} · {KIND_LABELS[prize.kind] ?? prize.kind}{prize.value_text ? ` · ${prize.value_text}` : ''}</p></div>
      <StatusPill label={STATUS_LABELS[prize.status] ?? prize.status} tone={statusTone(prize.status)} />
    </div>
    {share ? <p className="text-sm">{t`Your share: `}<strong>{share.amount}</strong> · {share.state === 'proposed' ? t`waiting for you to confirm`
      : share.state === 'confirmed' ? 'confirmed' : share.state}</p> : null}
    {payout ? <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4" aria-label={t`Your payout`}>
      <div><dt className="text-muted">{t`Prize (gross)`}</dt><dd>{payout.gross} {payout.currency}</dd></div>
      <div><dt className="text-muted">{t`Tax deducted`}</dt><dd>{payout.tds} {payout.currency}</dd></div>
      <div><dt className="text-muted">{t`Paid to you`}</dt><dd>{payout.net} {payout.currency}</dd></div>
      <div><dt className="text-muted">{t`Paid on`}</dt><dd>{payout.paidOn}</dd></div>
    </dl> : null}
    {claim && claim.state !== 'not_given' ? <p className="text-sm">{t`Payee details: ${claim.country} · ${claim.method.replace('_', ' ')}${claim.masked_details ? ` · ${claim.masked_details}` : ''}`}{claim.pan_masked ? t` · PAN ${claim.pan_masked}` : ''}
      {' · '}{claim.verified ? t`verified by finance` : t`waiting for finance to check`}</p> : null}
    {deadline && !payout ? <p className="text-sm text-muted">{deadline > new Date() ? t`Claim by ${when(prize.claim_deadline)}.`
      : t`The claim window closed on ${when(prize.claim_deadline)}.`}</p> : null}
    {mode === 'split' ? <PrizeSplitEditor makerspaceId={makerspaceId} eventId={prize.event_id} actorId={actorId} pending={pending}
      onCancel={() => setMode('idle')} onSubmit={shares => run(`prize-awards/${prize.award_id}/split/`, 0, { shares })} /> : null}
    {mode === 'claim' ? <PrizeClaimForm templates={prize.payee_templates} askPan={prize.tax_id_requested} pending={pending}
      onCancel={() => setMode('idle')} onSubmit={fields => run(`prize-awards/${prize.award_id}/claim/`, 0, fields)} /> : null}
    {mode === 'idle' ? <div className="flex flex-wrap gap-2">
      {can('confirm_share') && share ? <button type="button" className="desk-button-primary min-h-11" disabled={pending}
        onClick={() => run(`prize-shares/${share.id}/confirm/`, share.version)}>{t`Confirm my share`}</button> : null}
      {can('decline_share') && share ? <button type="button" className="desk-button min-h-11" disabled={pending}
        onClick={() => run(`prize-shares/${share.id}/decline/`, share.version)}>{t`Decline my share`}</button> : null}
      {can('propose_split') ? <button type="button" className="desk-button min-h-11" disabled={pending}
        onClick={() => setMode('split')}>{t`Split with my team`}</button> : null}
      {can('claim') ? <button type="button" className="desk-button-primary min-h-11" disabled={pending}
        onClick={() => setMode('claim')}>{claim && claim.state !== 'not_given' ? t`Change payee details` : t`Claim this prize`}</button> : null}
      {can('remove_claim') ? <button type="button" className="desk-button min-h-11" disabled={pending}
        onClick={() => run(`prize-awards/${prize.award_id}/claim/remove/`, 0)}>{t`Remove my payee details`}</button> : null}
    </div> : null}
  </article>;
}
