import { StatusPill } from '../../../components/ui';
import type { ResultRow } from './types';

/** Pairwise rounds show valid comparisons, the CrowdBT mean as the score and its uncertainty. */
export function CoverageTable({ rows, pairwise = false }: { rows: ResultRow[]; pairwise?: boolean }) {
  const headers = pairwise ? ['Project snapshot', 'Comparisons', 'Score (mean)', 'Uncertainty', 'Rank', 'Coverage']
    : ['Project snapshot', 'Views', 'Score', 'Rank', 'Coverage'];
  return <div className="overflow-x-auto rounded-xl border border-line"><table className="w-full text-left text-sm">
    <caption className="p-3 text-left font-semibold">{pairwise ? 'Valid comparisons and live standings (organisers only)' : 'Submitted nonconflicted views and results'}</caption>
    <thead><tr className="border-b border-line">{headers.map(label => <th key={label} scope="col" className="p-3">{label}</th>)}</tr></thead>
    <tbody>{rows.map(row => <tr key={row.snapshot_id} className="border-b border-line last:border-0">
      <th scope="row" className="p-3 font-medium">Project {row.snapshot_id}</th><td className="p-3">{row.n}</td>
      <td className="p-3 tabular-nums">{row.score ?? (pairwise ? 'Not compared yet' : 'No submitted score')}</td>
      {pairwise ? <td className="p-3 tabular-nums">± {row.sigma ?? '—'}</td> : null}<td className="p-3">{row.n ? row.rank : '—'}</td>
      <td className="p-3"><StatusPill label={row.coverage_complete ? 'Complete' : 'Needs review'} tone={row.coverage_complete ? 'success' : 'warn'} />
        {row.warnings.length ? <p className="mt-2 text-muted">{row.warnings.map(value => value.replace(/_/g, ' ')).join(', ')}</p> : null}
        {row.distribution ? <details className="mt-2"><summary className="min-h-11 cursor-pointer py-3">Score distribution</summary>
          <ul>{Object.entries(row.distribution).map(([score, count]) => <li key={score}>{score}: {count} submitted {count === 1 ? 'view' : 'views'}</li>)}</ul></details> : null}
      </td></tr>)}</tbody>
  </table></div>;
}
