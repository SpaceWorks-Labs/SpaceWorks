import { t } from "@lingui/core/macro";
import { ErrorBlock, Metric } from '../../../components/ui';
import { usePrizePool } from './hackmoneyApi';
import type { Scope } from './types';

/** G8: prize money announced against sponsorship earmarked to this event's pool, and what was paid, taxed, owed and recovered. */
export function PrizePoolPanel({ scope }: { scope: Scope }) {
  const pool = usePrizePool(scope, true);
  if (pool.isLoading) return <p role="status">{t`Loading prize pool…`}</p>;
  if (!pool.data) return <ErrorBlock error={pool.error} onRetry={() => void pool.refetch()} />;
  const data = pool.data; const money = (value: string) => `${value} ${data.currency.toUpperCase()}`;
  return <section className="grid gap-3" aria-label={t`Prize pool`}>
    <h3 className="title-section">{t`Prize pool`}</h3>
    <p className="text-sm text-muted">{t`Cash prizes the space pays. Prizes a sponsor pays the winner directly are never counted as space money.`}</p>
    <div className="grid gap-3 sm:grid-cols-3">
      <Metric label={t`Announced`} value={money(data.announced_total)} />
      <Metric label={t`Sponsor funding received`} value={money(data.sponsor_funded)} />
      <Metric label={t`Paid (gross)`} value={money(data.paid_gross)} />
      <Metric label={t`Tax deducted`} value={money(data.tds_recorded)} />
      <Metric label={t`Still owed`} value={money(data.owed)} danger={Number(data.owed) > 0} />
      <Metric label={t`Recovered`} value={money(data.recovered)} />
    </div>
    {data.sponsor_direct_awards ? <p className="text-sm">{t`${data.sponsor_direct_awards} award${data.sponsor_direct_awards === 1 ? '' : 's'} paid directly by sponsors.`}</p> : null}
  </section>;
}
