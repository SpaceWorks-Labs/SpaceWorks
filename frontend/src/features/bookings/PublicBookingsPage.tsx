import { AvailabilityCalendar } from "./AvailabilityCalendar";
import { PublicLayout, PublicDetailLayout } from "../../components/layouts";
import { publicPageChrome } from "../inventory/PublicPageChrome";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { PageMetadata } from "../../components/PageMetadata";
import { DiscoveryControls } from "../discovery/DiscoveryControls";
import { useDiscoveryState } from "../discovery/useDiscoveryState";
import { SpaceDiscoveryCalendar } from "./SpaceDiscoveryCalendar";
import { useLocation, useParams, useSearchParams } from "react-router-dom";

import { EmptyState, ListRow, StatusPill } from "../../components/ui";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { formatSlug } from "../inventory/PublicInventoryParts";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { publicErrorState } from "../inventory/publicErrorState";
import { PublicBookingForm } from "./PublicBookingForm";
import { usePublicSpaces, type PublicBookableSpace } from "./publicBookingsApi";

const KIND_LABELS: Record<PublicBookableSpace["kind"], string> = {
  dev_room: "Development room",
  bench: "Bench",
  meeting: "Meeting room",
  other: "Other",
};

export function PublicBookingsPage() {
  const { slug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const tenantPath = useTenantPath(makerspaceSlug);
  const location = useLocation();
  const canonicalPath = location.pathname.replace(/\/$/, "") === tenantPath().replace(/\/$/, "") ? tenantPath() : tenantPath("bookings");
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const spaces = usePublicSpaces(makerspaceSlug);
  const discovery = useDiscoveryState(bootstrap?.makerspace.timezone);
  const visibleSpaces = (spaces.error ? [] : spaces.data ?? []).filter((space) =>
    `${space.name} ${space.description} ${space.location}`.toLowerCase().includes(discovery.query.trim().toLowerCase())
    && (!Object.keys(KIND_LABELS).includes(discovery.facet) || space.kind === discovery.facet));
  const [params, setParams] = useSearchParams();
  const activeToken = params.get("space");
  const setActiveToken = (token: string | null) => { const next = new URLSearchParams(params); if (token) next.set("space", token); else next.delete("space"); setParams(next); };
  const selectedSpace = (spaces.error ? [] : spaces.data ?? []).find(space => space.public_token === activeToken);
  const displayName = bootstrap?.branding.display_name || bootstrap?.makerspace.name || formatSlug(makerspaceSlug) || "Makerspace";

  if (selectedSpace) return <div style={brandStyle}><PageMetadata title={`${selectedSpace.name} · ${displayName}`} description={selectedSpace.description} path={canonicalPath} image={selectedSpace.image_url || bootstrap?.makerspace.logo_url} siteName={displayName} /><PublicLayout {...publicPageChrome(makerspaceSlug, displayName, tenantPath, bootstrap)} state={{ status: "ready" }}
    breadcrumb={[{ label: "All spaces", href: tenantPath("bookings") }, { label: selectedSpace.name }]}>
    <PublicDetailLayout title={selectedSpace.name} state={{ status: "ready" }}
      cover={selectedSpace.image_url ? { src: selectedSpace.image_url, alt: "" } : undefined}
      chips={[{ label: KIND_LABELS[selectedSpace.kind] }, { label: selectedSpace.approval_mode === "approve" ? "Needs approval" : "Instant when available", tone: selectedSpace.approval_mode === "approve" ? "warn" : "success" }]}
      facts={selectedSpace.location ? [{ identity: { kind: "icon", icon: "Info", tone: "neutral" }, primary: selectedSpace.location, secondary: selectedSpace.capacity ? `Capacity ${selectedSpace.capacity}` : "Capacity not specified" }] : []}
      sections={[{ id: "about", label: "About this space", content: <p className="whitespace-pre-wrap leading-7">{selectedSpace.description}</p> },
        { id: "availability", label: "Availability", content: <AvailabilityCalendar makerspaceSlug={makerspaceSlug} publicToken={selectedSpace.public_token} /> }]}
      actionCard={{ title: "Choose a time", state: "open", form: <PublicBookingForm key={selectedSpace.public_token} makerspaceSlug={makerspaceSlug} space={selectedSpace} showCalendar={false} />,
        note: selectedSpace.approval_mode === "approve" ? "Your request stays pending until makerspace staff review it." : "A non-overlapping slot is confirmed immediately.",
        secondary: [{ label: "Close booking form", onClick: () => setActiveToken(null) }], mobileBar: { summary: selectedSpace.name, label: "Choose a time" } }} />
  </PublicLayout></div>;
  return <div style={brandStyle}>
    <PageMetadata title={`Bookings · ${displayName}`} description={`Discover public bookable rooms and benches at ${displayName}.`} path={canonicalPath} image={bootstrap?.makerspace.cover_image_url || bootstrap?.makerspace.logo_url} siteName={displayName} />
    <PublicLayout {...publicPageChrome(makerspaceSlug, displayName, tenantPath, bootstrap)}
      header={{ title: "Book a makerspace", subtitle: `Book a space at ${displayName}`, primary: { label: "My bookings", href: tenantPath("member/bookings") } }}
      state={spaces.isLoading ? { status: "loading" } : spaces.error ? publicErrorState(spaces.error, { noun: "Bookings" }, () => { void spaces.refetch(); }) : { status: "ready" }}>
      <DiscoveryControls state={discovery} searchLabel="Search spaces" filters={Object.entries(KIND_LABELS).map(([value, label]) => ({ value, label }))} />
      <p role="status" className="mb-4 text-sm text-muted">{visibleSpaces.length} matching space(s)</p>
      {!visibleSpaces.length ? <EmptyState message={spaces.data?.length ? "No spaces match these filters. Try another search." : "No bookable spaces yet. Check back soon."} /> : null}
      <div className="grid gap-4">{visibleSpaces.map(space => {
        const open = activeToken === space.public_token;
        return <article key={space.public_token}>
          <ListRow title={space.name} onClick={() => setActiveToken(space.public_token)} identity={space.image_url ? { kind: "image", src: space.image_url } : { kind: "icon", icon: "Calendar", tone: "neutral" }}
            meta={<>{space.location}<span className="mt-1 block">{space.description}</span><span className="mt-2 block">Capacity {space.capacity === 0 ? "not specified" : space.capacity} · {KIND_LABELS[space.kind]}</span></>}
            right={<div className="grid justify-items-end gap-3"><StatusPill label={space.approval_mode === "approve" ? "Needs approval" : "Instant when available"} tone={space.approval_mode === "approve" ? "warn" : "success"} />
              <button className="desk-button" type="button" aria-expanded={open} onClick={() => setActiveToken(open ? null : space.public_token)}>{open ? "Close booking form" : "Choose a time"}</button></div>} />
          {discovery.view === "calendar" && discovery.month ? <SpaceDiscoveryCalendar slug={makerspaceSlug} space={space} month={discovery.month} timeZone={discovery.timeZone} /> : null}
          {open ? <div className="mt-4"><PublicBookingForm key={space.public_token} makerspaceSlug={makerspaceSlug} space={space} /></div> : null}
        </article>;
      })}</div>
    </PublicLayout>
  </div>;
}
