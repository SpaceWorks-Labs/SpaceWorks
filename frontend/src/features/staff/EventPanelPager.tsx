/** Previous/next for an event drawer panel's paged list; hidden when everything fits on one page. */
export function EventPanelPager({ page, setPage, previous, next }: { page: number; setPage: (page: number) => void; previous?: string | null; next?: string | null }) {
  if (!previous && !next) return null;
  return <div className="flex flex-wrap gap-2">
    <button className="desk-button" type="button" disabled={!previous} onClick={() => setPage(page - 1)}>Previous</button>
    <button className="desk-button" type="button" disabled={!next} onClick={() => setPage(page + 1)}>Next</button>
  </div>;
}
