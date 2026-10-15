import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { EmptyState, ListRow, StatusPill } from "../../components/ui";
import { fetchPublicMakerspaces } from "../inventory/api";
import { tenantPath, useTenant } from "../../lib/tenant";

type SpaceRef = { makerspace: { slug: string } };

/** "Find a makerspace": every space in the platform's central directory, so a member can join
 * another one or ask for an invitation. The join rules (open, approval, vouch, invite-only) stay
 * on each space's own member page, so this list only links there and never decides eligibility.
 * Spaces hidden from the central directory are already excluded by the API; on a space's own
 * domain (single-tenant mode) the list is not shown at all. */
export function MakerspaceDiscovery({ currentSlug, memberships = [], requests = [] }: {
  currentSlug: string; memberships?: (SpaceRef & { membership_status: string })[]; requests?: (SpaceRef & { state: string })[];
}) {
  const tenant = useTenant();
  const [query, setQuery] = useState("");
  const spaces = useQuery({ queryKey: ["public", "makerspaces"], queryFn: fetchPublicMakerspaces, enabled: tenant.mode === "central", staleTime: 5 * 60_000 });
  if (tenant.mode !== "central") return null;
  const others = (spaces.data ?? []).filter(space => space.slug !== currentSlug);
  const needle = query.trim().toLocaleLowerCase();
  const shown = needle ? others.filter(space => `${space.name} ${space.location ?? ""}`.toLocaleLowerCase().includes(needle)) : others;
  const status = (slug: string) => {
    const membership = memberships.find(row => row.makerspace.slug === slug);
    if (membership) return <StatusPill label={membership.membership_status === "active" ? "Member" : membership.membership_status.replace(/_/g, " ")} tone={membership.membership_status === "active" ? "success" : "warn"} />;
    const request = requests.find(row => row.makerspace.slug === slug && !["rejected", "cancelled", "withdrawn", "expired"].includes(row.state));
    return request ? <StatusPill label="Request pending" tone="warn" /> : null;
  };
  return <section aria-labelledby="find-makerspace-title" className="desk-panel grid gap-4 p-5">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><h2 id="find-makerspace-title" className="title-panel">Find a makerspace</h2>
        <p className="mt-1 text-sm text-muted">Spaces on the platform. Open one to join or ask for an invitation.</p></div>
      {others.length > 6 ? <label className="grid gap-1 text-sm"><span className="sr-only">Search makerspaces</span>
        <input type="search" className="desk-input" placeholder="Search by name or place" value={query} onChange={event => setQuery(event.target.value)} /></label> : null}
    </div>
    {spaces.isLoading ? <p className="text-sm text-muted">Loading makerspaces…</p>
      : spaces.isError ? <p role="alert" className="text-sm text-danger">We couldn't load the makerspace list. <button type="button" className="underline" onClick={() => void spaces.refetch()}>Try again</button></p>
      : !shown.length ? <EmptyState message={needle ? "No makerspaces match that search." : "No other makerspaces are listed yet."} />
      : <ul className="grid gap-3">{shown.map(space => {
        const badge = status(space.slug);
        return <li key={space.slug}><ListRow title={space.name}
          identity={space.logo_url ? { kind: "image", src: space.logo_url } : { kind: "avatar", name: space.name, seed: space.slug }}
          meta={space.location || undefined} href={tenantPath("central", space.slug, "member")}
          right={<div className="flex items-center gap-3">{badge}<span className="text-sm font-semibold text-accent-ink">{badge ? "Open" : "Join or ask"}</span></div>} /></li>;
      })}</ul>}
  </section>;
}
