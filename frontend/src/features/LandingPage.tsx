import { useDeferredValue, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { PublicLayout } from "../components/layouts";
import { ThemeToggle } from "../components/ThemeToggle";
import { EmptyState } from "../components/ui";
import type { Makerspace } from "../types/inventory";
import { usePublicMakerspaces } from "./inventory/usePublicInventory";
import { LICENSE_URL } from "./inventory/PublicPageChrome";
import { LandingHero } from "./landing/LandingHero";
import { SpaceCard, SpaceCardSkeletons } from "./landing/SpaceCard";

function normalizeSearch(value: string) { return value.trim().toLowerCase().replace(/\s+/g, " "); }
function makerspaceSearchText(space: Makerspace) {
  return normalizeSearch([space.name, space.public_code, space.slug, space.location].filter(Boolean).join(" "));
}

/** The central welcome page: one teal brand field (hero), then every public space (spec §3). */
export function LandingPage() {
  const makerspacesQuery = usePublicMakerspaces();
  const [searchInput, setSearchInput] = useState("");
  const searchQuery = normalizeSearch(useDeferredValue(searchInput));
  const searchTokens = useMemo(() => searchQuery.split(" ").filter(Boolean), [searchQuery]);
  const indexed = useMemo(() => (makerspacesQuery.data ?? []).map(makerspace => ({ makerspace, searchText: makerspaceSearchText(makerspace) })), [makerspacesQuery.data]);
  const filtered = useMemo(() => indexed.filter(({ searchText }) => searchTokens.every(token => searchText.includes(token))).map(({ makerspace }) => makerspace), [indexed, searchTokens]);
  const total = makerspacesQuery.data?.length ?? 0;
  if (total === 1) return <Navigate replace to={`/m/${makerspacesQuery.data![0].slug}`} />;

  const clear = () => setSearchInput("");
  const emptyMessage = searchQuery ? `No spaces match '${searchQuery}'. Try another name or place.` : "No public spaces yet. They appear here once a space turns on its catalogue.";
  const loading = makerspacesQuery.isLoading;
  return <div className="sw-landing"><PublicLayout makerspace={{ name: "Space Works", slug: "", homeHref: "/" }} chrome="canvas"
    nav={[{ label: "About", href: "/about" }]} headerAction={{ label: "Sign in", href: "/member" }} liveStatus={<ThemeToggle variant="icon" />}
    state={makerspacesQuery.isError ? { status: "error", error: "Couldn't load spaces. Try again.", onRetry: () => { void makerspacesQuery.refetch(); } } : { status: "ready" }}
    hero={<LandingHero search={searchInput} onSearch={setSearchInput} shown={filtered.length} total={total} />}
    isEmpty={!loading && !filtered.length} empty={{ message: emptyMessage, action: searchQuery ? { label: "Clear search", onClick: clear } : undefined }}
    footer={{ credit: "Space Works · Made for shared workshops", links: [{ label: "About", href: "/about" }, { label: "License", href: LICENSE_URL, external: true }, { label: "Staff sign-in", href: "/admin" }] }}>
    <h2 className="title-panel mb-4 md:mb-6 min-[1680px]:text-2xl">All spaces</h2>
    {loading ? <SpaceCardSkeletons /> : filtered.length
      ? <div className="sw-space-grid">{filtered.map(space => <SpaceCard key={space.slug} space={space} />)}</div>
      : <EmptyState message={emptyMessage} action={searchQuery ? { label: "Clear search", onClick: clear } : undefined} />}
  </PublicLayout></div>;
}
