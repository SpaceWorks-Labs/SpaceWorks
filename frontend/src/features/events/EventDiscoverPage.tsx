import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { publicV1Request } from "../../lib/api";
import { SkipLink } from "../../components/SkipLink";

type Card = { title: string; description: string; url: string; image_url: string | null; date: string; location: string; availability: string; audience_label: string; registration_count?: number | null; makerspace_name?: string };
type Results = { count: number; next: string | null; previous: string | null; results: Card[] };

export function EventDiscoverPage() {
  const [filters, setFilters] = useState({ q: "", date_from: "", date_to: "" });
  const [draft, setDraft] = useState(filters);
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["event-discover", filters, page], staleTime: 0,
    queryFn: () => publicV1Request<Results>(`/discover/events/?${new URLSearchParams(Object.fromEntries(Object.entries({ ...filters, page: String(page) }).filter(([, value]) => value)))}`),
  });
  return <main className="desk-shell min-h-screen p-5"><SkipLink /><div id="main-content" className="mx-auto grid max-w-5xl gap-5">
    <Link className="desk-button w-fit" to="/">Home</Link><Link className="desk-button w-fit" to="/discover/bookings">Discover resources</Link><h1 className="title-page">Discover events</h1>
    <p className="text-muted">Public events from makerspaces on this deployment that opted into its directory.</p>
    <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); setPage(1); setFilters(draft); }}>
      <label>Search<input className="desk-input" maxLength={200} value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} /></label>
      <label>From<input className="desk-input" type="date" value={draft.date_from} onChange={(e) => setDraft({ ...draft, date_from: e.target.value })} /></label>
      <label>Through<input className="desk-input" type="date" value={draft.date_to} onChange={(e) => setDraft({ ...draft, date_to: e.target.value })} /></label>
      <button className="desk-button-primary">Find events</button>
    </form>
    {query.isLoading ? <p role="status">Loading events…</p> : null}
    {query.error ? <div role="alert"><p>Unable to discover events. Check your dates and try again.</p><button className="desk-button" onClick={() => query.refetch()}>Retry events</button></div> : null}
    {!query.error && query.data ? <><p>{query.data.count} events</p><div className="grid gap-4 md:grid-cols-2">
      {query.data.results.map((row) => <article className="rounded-xl border border-border p-4" key={row.url}>
        {row.image_url ? <img className="mb-3 h-40 w-full rounded-lg object-cover" alt="" src={row.image_url} /> : null}
        <h2 className="title-section"><a href={row.url} className="underline">{row.title}</a></h2><p>{row.makerspace_name}</p>
        <p>{new Date(row.date).toLocaleString()} · {row.location}</p><p>{row.availability}</p><p>{row.audience_label}</p>
        {row.registration_count != null ? <p>{row.registration_count} registered</p> : null}<p className="text-sm text-muted">{row.description}</p>
      </article>)}
    </div>{!query.data.results.length ? <p>No matching events.</p> : null}
      <nav aria-label="Discovery pages" className="flex gap-3"><button className="desk-button" disabled={!query.data.previous} onClick={() => setPage(page - 1)}>Previous</button><span>Page {page}</span><button className="desk-button" disabled={!query.data.next} onClick={() => setPage(page + 1)}>Next</button></nav></> : null}
  </div></main>;
}
