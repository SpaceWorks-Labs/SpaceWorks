import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { publicV1Request } from "../../lib/api";
import { SkipLink } from "../../components/SkipLink";

type Results = { count: number; next: string | null; previous: string | null; results: {
  title: string; description: string; url: string; location: string; makerspace_name: string;
}[] };
export function BookingDiscoverPage() {
  const [draft, setDraft] = useState({ q: "", kind: "", location: "" });
  const [filters, setFilters] = useState(draft);
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["booking-discover", filters, page], staleTime: 0,
    queryFn: () => publicV1Request<Results>(`/discover/bookings/?${new URLSearchParams(Object.fromEntries(Object.entries({ ...filters, page: String(page) }).filter(([, value]) => value)))}`),
  });
  return <main className="desk-shell min-h-screen p-5"><SkipLink /><div className="mx-auto grid max-w-5xl gap-5" id="main-content">
    <nav className="flex gap-3"><Link to="/" className="desk-button">Home</Link><Link to="/discover" className="desk-button">Discover events</Link></nav>
    <h1 className="title-page">Discover resources</h1><p>Rooms and benches from makerspaces on this deployment that opted into its directory.</p>
    <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); setFilters(draft); setPage(1); }}>
      <label>Search resources<input className="desk-input" maxLength={200} value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} /></label>
      <label>Kind<select className="desk-input" value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value })}><option value="">All resources</option><option value="dev_room">Development room</option><option value="meeting">Meeting room</option><option value="bench">Bench</option><option value="other">Other</option></select></label>
      <label>Location<input className="desk-input" maxLength={255} value={draft.location} onChange={(e) => setDraft({ ...draft, location: e.target.value })} /></label>
      <button className="desk-button-primary">Search</button>
    </form>
    {query.isLoading ? <p role="status">Loading resources…</p> : null}
    {query.error ? <div role="alert"><p>Unable to discover resources.</p><button className="desk-button" onClick={() => query.refetch()}>Retry</button></div> : null}
    {!query.error && query.data ? <><p>{query.data.count} resources</p><div className="grid gap-4 md:grid-cols-2">{query.data.results.map((row) => <article key={row.url} className="desk-panel p-4"><h2 className="title-section"><a className="underline" href={row.url}>{row.title}</a></h2><p>{row.makerspace_name} · {row.location}</p><p>{row.description}</p></article>)}</div>
      {!query.data.count ? <p>No matching resources.</p> : null}<nav aria-label="Resource discovery pages" className="flex gap-3"><button className="desk-button" disabled={!query.data.previous} onClick={() => setPage(page - 1)}>Previous</button><span>Page {page}</span><button className="desk-button" disabled={!query.data.next} onClick={() => setPage(page + 1)}>Next</button></nav></> : null}
  </div></main>;
}
