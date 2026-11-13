import { plural, t } from "@lingui/core/macro";
import { ArrowRight, RotateCcw } from 'lucide-react';
import { Callout, StatusPill } from '../../../components/ui';
import type { Round } from './types';

type Pair = { snapshot_id: number; judge_role_assignment_id: number };
/** The dry-run answer of `judging-rounds/<id>/assign/` (E-B4, D10). */
export type AssignPlan = { pairs: Pair[]; dropped?: Pair[]; deficits: Record<string, number>; coverage_complete: boolean;
  before_loads?: Record<string, number>; after_loads?: Record<string, number>; existing?: 'keep' | 'replace'; plan_fingerprint?: string };

// `deficits` maps a project id to how many more judge assignments it still needs.
export function deficitText(deficits: unknown) {
  const rows = deficits && typeof deficits === 'object' ? Object.entries(deficits as Record<string, number>) : [];
  const list = rows.map(([project, needed]) => t`project #${project} needs ${needed} more`).join(', ');
  return list ? t`More judges are needed: ${list}.` : t`More judges are needed.`;
}

function loadRows(plan: AssignPlan) {
  const before = plan.before_loads ?? {}, after = plan.after_loads ?? {};
  return [...new Set([...Object.keys(before), ...Object.keys(after)])].sort((a, b) => Number(a) - Number(b))
    .map(judge => ({ judge, before: before[judge] ?? 0, after: after[judge] ?? 0 }));
}

/** D10: what the planned assignment does to each judge's workload, what it withdraws, and the guarded apply. */
export function AssignmentPreview({ round, plan, pending, stale, onApply, onPreviewAgain, onDiscard }: {
  round: Round; plan: AssignPlan; pending: boolean; stale: boolean;
  onApply: () => void; onPreviewAgain: () => void; onDiscard: () => void }) {
  const rows = loadRows(plan); const dropped = plan.dropped ?? [];
  return <section className="grid gap-4 rounded-xl border border-outline bg-surface p-4" aria-label={t`Assignment preview for ${round.key}`}>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h4 className="title-section">{t`Preview: ${round.key}`}</h4>
      <StatusPill tone={plan.coverage_complete ? 'success' : 'warn'} label={plan.coverage_complete ? t`Full coverage` : t`Short of judges`} />
    </div>
    <p className="text-sm text-ink">{plural(plan.pairs.length, { one: '# new assignment', other: '# new assignments' })}
      {dropped.length ? ` · ${plural(dropped.length, { one: '# unscored assignment replaced', other: '# unscored assignments replaced' })}` : ''}
      {' · '}{plan.existing === 'replace' ? t`Unscored work is re-planned; scored work stays.` : t`Current assignments stay and count towards the target.`}</p>
    {!plan.coverage_complete ? <p className="text-sm text-warn-ink">{deficitText(plan.deficits)}</p> : null}
    {rows.length ? <div className="overflow-x-auto rounded-xl border border-line bg-panel"><table className="w-full text-left text-sm">
      <caption className="p-3 text-left font-semibold">{t`Projects per judge, before and after`}</caption>
      <thead><tr className="border-b border-line">
        <th scope="col" className="p-3">{t`Judge`}</th><th scope="col" className="p-3 text-right">{t`Now`}</th>
        <th scope="col" className="p-3 text-right">{t`After`}</th><th scope="col" className="p-3 text-right">{t`Change`}</th></tr></thead>
      <tbody>{rows.map(row => { const change = row.after - row.before; return <tr key={row.judge} className="border-b border-line last:border-0">
        <th scope="row" className="p-3 font-medium">{t`Judge ${row.judge}`}</th>
        <td className="p-3 text-right tabular-nums">{row.before}</td>
        <td className="p-3 text-right tabular-nums"><span className="inline-flex items-center gap-1"><ArrowRight aria-hidden="true" className="size-3 text-muted" />{row.after}</span></td>
        <td className={`p-3 text-right font-semibold tabular-nums ${change > 0 ? 'text-accent-ink' : change < 0 ? 'text-warn-ink' : 'text-muted'}`}>
          {change > 0 ? `+${change}` : change === 0 ? '0' : change}</td></tr>; })}</tbody>
    </table></div> : null}
    {dropped.length ? <details className="rounded-xl border border-line bg-panel p-3"><summary className="min-h-11 cursor-pointer py-2 font-semibold">
      {plural(dropped.length, { one: '# assignment would be withdrawn', other: '# assignments would be withdrawn' })}</summary>
      <ul className="mt-2 grid gap-1 text-sm">{dropped.map(pair => <li key={`${pair.snapshot_id}:${pair.judge_role_assignment_id}`}>
        {t`Project ${pair.snapshot_id} from judge ${pair.judge_role_assignment_id}`}</li>)}</ul>
      <p className="mt-2 text-xs text-muted">{t`Only unscored assignments are withdrawn. Each judge is told the project left their list.`}</p></details> : null}
    {stale ? <Callout size="inline" tone="warn" lead={t`This preview is out of date.`}
      body={t`Something changed since you previewed it: a score came in, a judge changed or the round moved. Preview again before applying.`} /> : null}
    <div className="flex flex-wrap gap-2">
      {stale ? <button type="button" className="desk-button-primary inline-flex min-h-11 items-center gap-2" disabled={pending} onClick={onPreviewAgain}>
        <RotateCcw aria-hidden="true" className="size-4" />{t`Preview again`}</button>
        : <button type="button" className="desk-button-primary min-h-11" disabled={pending || !plan.coverage_complete || !plan.plan_fingerprint} onClick={onApply}>
          {t`Apply this plan`}</button>}
      <button type="button" className="desk-button min-h-11" disabled={pending} onClick={onDiscard}>{t`Discard preview`}</button>
    </div>
  </section>;
}
