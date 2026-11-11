import { t } from "@lingui/core/macro";
import { ErrorBlock, StatusPill } from '../../../components/ui';
import type { PrizePayableAwardRead } from '../../../generated/api';
import { usePrizeAwardActions } from './hackmoneyApi';
import { ForfeitForm, FulfilForm, PayoutForm, SplitEditor } from './PrizeAwardForms';
import type { Scope } from './types';

const STATUS: Record<PrizePayableAwardRead['status'], [string, 'success' | 'warn' | 'neutral' | 'danger']> = {
  owed: ['Owed', 'warn'], part_paid: ['Partly paid', 'warn'], paid: ['Paid', 'success'], fulfilled: ['Handed over', 'success'],
  sponsor_paid: ['Paid by sponsor', 'success'], forfeited: ['Forfeited', 'neutral'],
};
const KINDS = (): Record<string, string> => ({ cash: t`Cash`, item: t`Item`, credit: t`Credit`, perk: t`Perk` });

/** One announced award: what it is, who shares it, and the one action that settles it. */
export function PrizeAwardCard({ scope, award, claims, recording, onRecord }: { scope: Scope; award: PrizePayableAwardRead; claims: boolean;
  recording: boolean; onRecord: (fields: Record<string, unknown>) => void }) {
  const actions = usePrizeAwardActions(scope);
  const [label, tone] = STATUS[award.status] ?? [award.status, 'neutral'];
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
    <p className="text-sm">{KINDS()[award.kind] ?? award.kind}{award.funding === 'sponsor_direct' ? t` · paid by the sponsor` : ''}
      {award.amount_per_winner && award.kind === 'cash' ? ` · ${award.amount_per_winner}` : ''}{award.value_text ? ` · ${award.value_text}` : ''}</p>
    {award.shares.length ? <ul className="grid gap-1 text-sm" aria-label={t`Shares`}>{award.shares.map(share =>
      <li key={share.id}>{t`Member #${share.member_id ?? '—'}: ${share.amount} · ${share.state}`}{share.paid ? t` · paid` : ''}</li>)}</ul> : null}
    <ErrorBlock error={actions.split.error || actions.fulfil.error || actions.forfeit.error} />
    {open && cash ? <PayoutForm award={award} recipients={unpaidConfirmed} busy={busy}
      onSubmit={fields => onRecord({ award_id: award.id, ...fields })} /> : null}
    {open && !cash ? <FulfilForm sponsor={award.funding === 'sponsor_direct'} busy={busy}
      onSubmit={fields => actions.fulfil.mutate({ awardId: award.id, fields })} /> : null}
    {open && cash && claims && !award.shares.some(share => share.paid) ? <SplitEditor total={award.amount_per_winner} busy={busy}
      onSubmit={shares => actions.split.mutate({ awardId: award.id, shares })} /> : null}
    {open ? <ForfeitForm shares={award.shares.filter(share => !share.paid && share.state !== 'forfeited')} busy={busy}
      onSubmit={(note, shareId) => actions.forfeit.mutate({ awardId: award.id, note, shareId })} /> : null}
  </article>;
}
