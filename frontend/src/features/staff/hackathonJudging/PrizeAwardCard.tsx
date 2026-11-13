import { t } from "@lingui/core/macro";
import { ErrorBlock, StatusPill } from '../../../components/ui';
import type { PrizePayableAwardRead } from '../../../generated/api';
import { usePrizeAwardActions } from './hackmoneyApi';
import { prizeKindLabel, prizeStatusLabel, shareStateLabel } from './prizeLabels';
import { formatMoney } from '../../../lib/money';
import { ForfeitForm, FulfilForm, PayoutForm, SplitEditor } from './PrizeAwardForms';
import type { Scope } from './types';

const TONE: Record<PrizePayableAwardRead['status'], 'success' | 'warn' | 'neutral' | 'danger'> = {
  owed: 'warn', part_paid: 'warn', paid: 'success', fulfilled: 'success', sponsor_paid: 'success', forfeited: 'neutral',
};

/** One announced award: what it is, who shares it, and the one action that settles it. */
export function PrizeAwardCard({ scope, award, claims, recording, currency = '', onRecord }: { scope: Scope; award: PrizePayableAwardRead; claims: boolean;
  recording: boolean; currency?: string; onRecord: (fields: Record<string, unknown>) => void }) {
  const actions = usePrizeAwardActions(scope);
  const label = prizeStatusLabel(award.status), tone = TONE[award.status] ?? 'neutral';
  const cash = award.kind === 'cash' && award.funding === 'space';
  const open = award.status === 'owed' || award.status === 'part_paid';
  const unpaidConfirmed = award.shares.filter(share => share.state === 'confirmed' && !share.paid);
  const busy = recording || actions.split.isPending || actions.fulfil.isPending || actions.forfeit.isPending;
  return <article className="grid gap-3 rounded-xl border border-line p-4" aria-label={t`${award.prize_name}, rank ${award.rank}`}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div><p className="font-semibold">{t`${award.prize_name} · rank ${award.rank}`}</p><p className="text-sm text-muted">{award.title}</p></div>
      <div className="flex flex-wrap gap-2"><StatusPill label={label} tone={tone} />
        {award.open_recoveries ? <StatusPill label={t`${award.open_recoveries} owed back`} tone="danger" /> : null}</div>
    </div>
    <p className="text-sm">{prizeKindLabel(award.kind)}{award.funding === 'sponsor_direct' ? t` · paid by the sponsor` : ''}
      {award.amount_per_winner && award.kind === 'cash' ? ` · ${formatMoney(award.amount_per_winner, currency)}` : ''}{award.value_text ? ` · ${award.value_text}` : ''}</p>
    {award.shares.length ? <ul className="grid gap-1 text-sm" aria-label={t`Shares`}>{award.shares.map(share =>
      <li key={share.id}>{t`Member #${share.member_id ?? '—'}: ${formatMoney(share.amount, currency)} · ${shareStateLabel(share.state)}`}{share.paid ? t` · paid` : ''}</li>)}</ul> : null}
    <ErrorBlock error={actions.split.error || actions.fulfil.error || actions.forfeit.error} />
    {open && cash ? <PayoutForm award={award} recipients={unpaidConfirmed} busy={busy} currency={currency}
      onSubmit={fields => onRecord({ award_id: award.id, ...fields })} /> : null}
    {open && !cash ? <FulfilForm sponsor={award.funding === 'sponsor_direct'} busy={busy}
      onSubmit={fields => actions.fulfil.mutate({ awardId: award.id, fields })} /> : null}
    {open && cash && claims && !award.shares.some(share => share.paid) ? <SplitEditor total={award.amount_per_winner} busy={busy} currency={currency}
      onSubmit={shares => actions.split.mutate({ awardId: award.id, shares })} /> : null}
    {open ? <ForfeitForm shares={award.shares.filter(share => !share.paid && share.state !== 'forfeited')} busy={busy}
      onSubmit={(note, shareId) => actions.forfeit.mutate({ awardId: award.id, note, shareId })} /> : null}
  </article>;
}
