import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { PublicDetailLayout, PublicLayout } from "../../components/layouts";
import { PageMetadata } from "../../components/PageMetadata";
import type { QueryState } from "../../components/ui";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { getAccessToken, refreshAccessToken } from "../../lib/api";
import { publicPageChrome } from "../inventory/PublicPageChrome";
import { formatSlug } from "../inventory/PublicInventoryParts";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { AvailabilityCalendar } from "./AvailabilityCalendar";
import { PublicBookingForm } from "./PublicBookingForm";
import { BookingResourceWebsite } from "./BookingResourceWebsite";
import { usePublicBookingResource } from "./bookingWebsiteApi";
import { photosSection } from "./spacePhotosSection";

export function PublicBookingResourcePage() {
  const { slug = "", resourceToken = "" } = useParams();
  const tenant = useTenant();
  const tenantSlug = tenant.mode === "single" ? tenant.slug : slug;
  const path = useTenantPath(tenantSlug);
  // Central routes load the tenant bootstrap themselves so the header carries the brand and programme nav.
  const bootstrapQuery = useTenantBootstrap(tenantSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const displayName = bootstrap?.branding.display_name || bootstrap?.makerspace.name || formatSlug(tenantSlug) || "Makerspace";
  const [session, setSession] = useState<"restoring" | "authenticated" | "anonymous">(() => getAccessToken() ? "authenticated" : "restoring");
  useEffect(() => {
    let active = true;
    if (!getAccessToken()) {
      void refreshAccessToken().then((restored) => {
        if (active) setSession(restored ? "authenticated" : "anonymous");
      }).catch(() => { if (active) setSession("anonymous"); });
    }
    return () => { active = false; };
  }, []);
  // A canonical tenant-prefixed link on a single-site installation stays tenant-bound.
  const valid = tenant.mode !== "single" || !slug || slug === tenant.slug;
  const query = usePublicBookingResource(valid ? tenantSlug : "", resourceToken);
  const resource = !valid || query.error ? undefined : query.data;
  // An unavailable resource never says whether it is private or gone; Retry only where a refetch can help.
  const state: QueryState = valid && query.isLoading ? { status: "loading" }
    : !valid || query.error ? { status: "error", error: "Resource unavailable. This resource may be private or no longer available.",
      onRetry: valid ? () => { void query.refetch(); } : undefined }
    : { status: "ready" };
  const approval = resource?.approval_mode === "approve";
  return <div style={brandStyle}>
    {resource ? <PageMetadata title={resource.name} description={resource.description} image={resource.image_url} path={path(`bookings/${resourceToken}`)} /> : null}
    <PublicLayout {...publicPageChrome(tenantSlug, displayName, path, bootstrap)} state={state}
      breadcrumb={[{ label: "All resources", href: path("bookings") }, { label: resource?.name ?? "Resource" }]}>
      <PublicDetailLayout title={resource?.name ?? (state.status === "error" ? "Resource unavailable" : "Resource")} state={state}
        cover={resource?.image_url ? { src: resource.image_url, alt: "" } : undefined}
        chips={resource ? [{ label: approval ? "Needs approval" : "Instant when available", tone: approval ? "warn" : "success" }] : []}
        facts={resource?.location ? [{ identity: { kind: "icon", icon: "Info", tone: "neutral" }, primary: resource.location,
          secondary: resource.capacity ? `Capacity ${resource.capacity}` : "Capacity not specified" }] : []}
        sections={resource ? [
          ...photosSection(resource),
          { id: "about", label: "About this resource", content: <p className="whitespace-pre-wrap leading-7">{resource.description}</p> },
          { id: "rules", label: "Booking rules", content: <div className="grid gap-2 leading-7">
            <p>{resource.rules.minimum_minutes}–{resource.rules.maximum_minutes} minutes; request at least {resource.rules.lead_minutes} minutes ahead, up to {resource.rules.advance_days} days ahead.</p>
            <p>Changes and cancellation close {resource.rules.cancellation_cutoff_hours} hours before the start. {approval ? "Staff approval is required." : "Available times confirm immediately."}</p>
          </div> },
          ...(resource.website ? [{ id: "details", label: "Resource details", content: <BookingResourceWebsite page={resource.website} slug={tenantSlug} /> }] : []),
          { id: "availability", label: "Availability", content: <AvailabilityCalendar makerspaceSlug={tenantSlug} publicToken={resource.public_token} /> },
        ] : []}
        actionCard={{ title: "Choose a time", state: "open",
          summary: resource ? <div className="flex flex-wrap items-end gap-6">
            <dl><dt className="eyebrow">Capacity</dt><dd className="font-semibold tabular-nums text-ink">{resource.capacity || "Not specified"}</dd></dl>
            <dl><dt className="eyebrow">Flat price</dt><dd className="font-semibold tabular-nums text-ink">{resource.payment_amount} {resource.currency.toUpperCase()}</dd></dl>
          </div> : null,
          form: !resource ? null : session === "restoring" ? <p role="status" className="text-sm text-muted">Restoring your session...</p>
            : session === "anonymous" ? <MemberAuthPanel embedded context={<p className="text-sm text-muted">Sign in to submit a booking.</p>}
              makerspaceSlug={tenantSlug} onAuthenticated={() => setSession("authenticated")} />
            : <PublicBookingForm key={resourceToken} makerspaceSlug={tenantSlug} space={resource} showCalendar={false} />,
          note: approval ? "Your request stays pending until makerspace staff review it." : "A non-overlapping slot is confirmed immediately.",
          mobileBar: { summary: resource?.name ?? "Resource", label: "Choose a time" } }} />
    </PublicLayout>
  </div>;
}
