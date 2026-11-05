export type StageFunnelRow = { position: number; name: string; submitted: number; eligible: number; shortlisted: number | null; advanced: number | null };

const cell = (value: number | null) => (value === null ? "—" : value);

/** S16: counts only, per submission stage: submitted, eligible, shortlisted and teams that went on. */
export function StageFunnel({ rows }: { rows: readonly StageFunnelRow[] }) {
  return <div className="overflow-x-auto"><table className="w-full text-left text-sm">
    <caption className="mb-2 text-left font-semibold">Submission stages</caption>
    <thead><tr><th scope="col" className="p-2">Stage</th><th scope="col" className="p-2">Submitted</th><th scope="col" className="p-2">Eligible</th>
      <th scope="col" className="p-2">Shortlisted</th><th scope="col" className="p-2">Went on</th></tr></thead>
    <tbody>{rows.map(row => <tr key={row.position}><th scope="row" className="p-2 font-normal">{`${row.position}. ${row.name}`}</th>
      <td className="p-2 tabular-nums">{row.submitted}</td><td className="p-2 tabular-nums">{row.eligible}</td>
      <td className="p-2 tabular-nums">{cell(row.shortlisted)}</td><td className="p-2 tabular-nums">{cell(row.advanced)}</td></tr>)}</tbody>
  </table><p className="text-xs text-muted">A dash means the stage has no shortlist, or it is the last stage.</p></div>;
}
