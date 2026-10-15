import { useDeferredValue, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { PublicLayout } from "../components/layouts";
import { MakerspaceBrand } from "../components/MakerspaceBrand";
import { MakerspaceMapLink } from "../components/MakerspaceMapLink";
import { ThemeToggle } from "../components/ThemeToggle";
import { EmptyState, Field, StatusPill } from "../components/ui";
import type { Makerspace } from "../types/inventory";
import { usePublicMakerspaces } from "./inventory/usePublicInventory";

function normalizeSearch(value: string) { return value.trim().toLowerCase().replace(/\s+/g, " "); }
function makerspaceSearchText(space: Makerspace) {
  return normalizeSearch([space.name, space.public_code, space.slug, space.location].filter(Boolean).join(" "));
}

export function LandingPage() {
  const makerspacesQuery = usePublicMakerspaces();
  const [searchInput, setSearchInput] = useState("");
  const searchQuery = normalizeSearch(useDeferredValue(searchInput));
  const searchTokens = useMemo(() => searchQuery.split(" ").filter(Boolean), [searchQuery]);
  const indexed = useMemo(() => (makerspacesQuery.data ?? []).map(makerspace => ({ makerspace, searchText: makerspaceSearchText(makerspace) })), [makerspacesQuery.data]);
  const filtered = useMemo(() => indexed.filter(({ searchText }) => searchTokens.every(token => searchText.includes(token))).map(({ makerspace }) => makerspace), [indexed, searchTokens]);
  const total = makerspacesQuery.data?.length ?? 0;
  if (total === 1) return <Navigate replace to={`/m/${makerspacesQuery.data![0].slug}`} />;

  const searchToolbar = <form role="search" className="mb-8 flex flex-wrap items-end gap-3" onSubmit={event => event.preventDefault()}>
      <Field label="Search makerspaces" className="min-w-0 flex-1" hint="Search by name, code or place.">
        <input className="desk-input w-full" type="search" placeholder="Search by name, code or place" value={searchInput} onChange={event => setSearchInput(event.target.value)} />
      </Field>
      {searchInput ? <button className="desk-button" type="button" onClick={() => setSearchInput("")}>Clear search</button> : null}
      <p className="py-3 text-sm tabular-nums text-muted" aria-live="polite">{filtered.length} / {total} spaces</p>
    </form>;
  return <div className="[&_h1]:font-accent"><PublicLayout makerspace={{ name: "Space Works", slug: "", homeHref: "/" }}
    nav={[{ label: "About", href: "/about" }]} headerAction={{ label: "Sign in", href: "/member" }} liveStatus={<ThemeToggle />}
    state={makerspacesQuery.isLoading ? { status: "loading" } : makerspacesQuery.isError ? { status: "error", error: "Couldn't load spaces. Try again.", onRetry: () => { void makerspacesQuery.refetch(); } } : { status: "ready" }}
    header={{ eyebrow: "Space Works", title: "Find a space. Borrow the tool.", subtitle: "Public catalogues from community workshops, labs and makerspaces.", meta: searchToolbar }}
    isEmpty={!filtered.length} empty={{ message: searchQuery ? `No spaces match '${searchQuery}'. Try another name or place.` : "No public spaces yet. They appear here once a space turns on its catalogue.", action: searchQuery ? { label: "Clear search", onClick: () => setSearchInput("") } : undefined }}
    footer={{ credit: "Space Works · Made for shared workshops", links: [{ label: "About", href: "/about" }, { label: "Staff sign-in", href: "/admin" }] }}>
    <LandingSpaces spaces={filtered} search={searchQuery} clear={() => setSearchInput("")} />
  </PublicLayout></div>;
}

function LandingSpaces({ spaces, search, clear }: { spaces: Makerspace[]; search: string; clear: () => void }) {
  if (!spaces.length) return <EmptyState message={search ? `No spaces match '${search}'. Try another name or place.` : "No public spaces yet. They appear here once a space turns on its catalogue."}
    action={search ? { label: "Clear search", onClick: clear } : undefined} />;
  return <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">{spaces.map(space => <article key={space.slug} className="group relative flex min-w-0 flex-col rounded-xl border border-line bg-panel">
    <div className="relative aspect-[1.8] overflow-hidden rounded-t-xl bg-brand-soft">
      {space.cover_image_url ? <img src={space.cover_image_url} alt={`${space.name} cover`} loading="lazy" className="h-full w-full object-cover" /> : <div className="grid h-full place-items-center font-display text-5xl text-brand-ink" aria-hidden="true">{space.name.charAt(0)}</div>}
      <div className="absolute left-4 top-4"><StatusPill label="Public catalogue" tone="success" /></div>
    </div>
    <div className="flex flex-1 flex-col gap-3 p-6">
      <MakerspaceBrand name={space.name} logoUrl={space.logo_url} size="md" />
      <MakerspaceMapLink makerspace={space} className="relative z-10" locationClassName="break-words text-sm text-muted" />
      <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-4">
        <span className="text-sm tabular-nums text-muted">{space.public_code}</span>
        <Link className="desk-button-ghost after:absolute after:inset-0 after:rounded-xl after:content-['']" to={`/m/${space.slug}`} aria-label={`Open ${space.name} catalog`}>Open catalogue →</Link>
      </div>
    </div>
  </article>)}</div>;
}
