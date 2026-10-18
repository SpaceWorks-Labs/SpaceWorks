import { useState } from "react";
import { usePageRevisions } from "./pageApi";
import type { PageOwner } from "./pageTypes";
import { Pagination } from "../../components/ui";
import { sectionLabels } from "./documentDefaults";

export function PageRevisionHistory({ owner }: { owner: PageOwner }) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const query = usePageRevisions(owner, open, page);
  return <section className="grid gap-3" aria-label="Revision history">
    <button type="button" className="desk-button justify-self-start" aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? "Hide revision history" : "Show revision history"}</button>
    {open ? <>
      {query.isLoading ? <p role="status">Loading revision history…</p> : null}
      {query.error ? <p role="alert">Couldn't load history. <button type="button" className="desk-button" onClick={() => { void query.refetch(); }}>Retry</button></p> : null}
      {!query.error && query.data ? <><ol className="grid gap-2">{query.data.results.map(row => <li key={row.id} className="rounded-xl border border-line p-3 text-sm"><time dateTime={row.created_at}>{new Date(row.created_at).toLocaleString()}</time> · {row.created_by_display ?? "Former editor"}<p>{row.summary.section_types.map(type => sectionLabels[type]).join(", ") || "No sections"}</p></li>)}</ol>
        {!query.data.count ? <p className="text-sm text-muted">No saved revisions yet.</p> : null}
        <Pagination page={page} pageSize={24} count={query.data.count} totalPages={Math.ceil(query.data.count / 24)} onChange={setPage} /></> : null}
    </> : null}
  </section>;
}
