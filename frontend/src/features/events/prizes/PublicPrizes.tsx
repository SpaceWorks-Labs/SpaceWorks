import { t } from "@lingui/core/macro";
import { Gift } from 'lucide-react';
import type { PublicPrizeRead } from '../../../generated/api';
import { KIND_LABELS } from './api';

/** Public prize list (hack-money G6). The page fetches with `usePublicPrizes` and adds this block only
 *  when rows came back: a 404 (the organiser keeps prizes private) yields none, so nothing renders. */
export function PublicPrizes({ rows }: { rows: PublicPrizeRead[] }) {
  if (!rows.length) return null;
  return <div className="grid gap-3" aria-label={t`Prizes`}>
    <p className="flex items-center gap-2 text-sm text-muted"><Gift className="text-accent" aria-hidden="true" />{t`What the winners take home`}</p>
    <ul className="grid gap-3 sm:grid-cols-2">
      {rows.map((row, index) => <li key={`${row.name}-${index}`} className="grid gap-1 rounded-xl border border-line bg-panel p-4">
        <p className="font-semibold">{row.name}</p>
        {row.track || row.sponsor ? <p className="text-sm text-muted">{[row.track, row.sponsor && `Sponsored by ${row.sponsor}`].filter(Boolean).join(' · ')}</p> : null}
        <p className="text-sm">{row.kind === 'cash' && row.amount_per_winner
          ? t`${row.amount_per_winner} ${row.currency.toUpperCase()} per winner`
          : `${KIND_LABELS[row.kind] ?? row.kind}${row.value_text ? `: ${row.value_text}` : ''}`}
          {row.award_count > 1 ? t` · ${row.award_count} winners` : ''}</p>
      </li>)}
    </ul>
  </div>;
}
