import { StatusPill } from '../../../components/ui';
import type { ResultRow } from './types';

export function CoverageTable({ rows }: { rows: ResultRow[] }) {
  return <div className="overflow-x-auto rounded-xl border border-line"><table className="w-full text-left text-sm">
    <caption className="p-3 text-left font-semibold">Submitted nonconflicted views and results</caption>
    <thead><tr className="border-b border-line">{['Project snapshot', 'Views', 'Score', 'Rank', 'Coverage'].map(label => <th key={label} scope="col" className="p-3">{label}</th>)}</tr></thead>
    <tbody>{rows.map(row => <tr key={row.snapshot_id} className="border-b border-line last:border-0">
      <th scope="row" className="p-3 font-medium">Project {row.snapshot_id}</th><td className="p-3">{row.n}</td>
      <td className="p-3 tabular-nums">{row.score ?? 'No submitted score'}</td><td className="p-3">{row.n ? row.rank : '—'}</td>
      <td className="p-3"><StatusPill label={row.coverage_complete ? 'Complete' : 'Needs review'} tone={row.coverage_complete ? 'success' : 'warn'} />
        {row.warnings.length ? <p className="mt-2 text-muted">{row.warnings.map(value => value.replace(/_/g, ' ')).join(', ')}</p> : null}
        {row.distribution ? <details className="mt-2"><summary className="min-h-11 cursor-pointer py-3">Score distribution</summary>
          <ul>{Object.entries(row.distribution).map(([score, count]) => <li key={score}>{score}: {count} submitted {count === 1 ? 'view' : 'views'}</li>)}</ul></details> : null}
      </td></tr>)}</tbody>
  </table></div>;
}
