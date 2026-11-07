import { t } from "@lingui/core/macro";
import { ErrorBlock } from '../../../components/ui';
import { useMissingTeamCharges } from './hackmoneyApi';
import type { Scope } from './types';

/** G15: confirmed teams whose team charge was never raised. Raising is idempotent and charges the leader once. */
export function TeamChargesPanel({ scope }: { scope: Scope }) {
  const { list, raise } = useMissingTeamCharges(scope, true);
  const rows = list.data?.results ?? [];
  if (!list.isLoading && !rows.length && !list.error) return null;
  return <section className="grid gap-3" aria-label={t`Missing team charges`}>
    <h3 className="title-section">{t`Team charges not raised`}</h3>
    <p className="text-sm text-muted">{t`These confirmed teams owe the team price, but their charge was never raised. Raise it now; the leader is charged once.`}</p>
    <ErrorBlock error={list.error || raise.error} />
    <ul className="grid gap-2">{rows.map(row => <li key={row.team_id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line p-3">
      <span className="text-sm">{t`${row.team_name} · leader #${row.leader_id}${row.amount ? ` · ${row.amount} ${row.currency.toUpperCase()}` : ''}`}</span>
      <button type="button" className="desk-button min-h-11" disabled={raise.isPending} onClick={() => raise.mutate(row.team_id)}>{t`Raise charge now`}</button>
    </li>)}</ul>
  </section>;
}
