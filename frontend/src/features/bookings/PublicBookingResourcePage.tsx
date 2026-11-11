import { t } from "@lingui/core/macro";
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
import { chargesOn } from "../../lib/charges";
import { formatMoney } from "../../lib/money";
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
  const showPrice = chargesOn(bootstrap, "bookings"); // #184: free bookings show no price
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
    : !valid || query.error ? { status: "error", error: t`Resource unavailable. This resource may be private or no longer available.`,
      onRetry: valid ? () => { void query.refetch(); } : undefined }
    : { status: "ready" };
  const approval = resource?.approval_mode === "approve";
  return <div style={brandStyle}>
    {resource ? <PageMetadata title={resource.name} description={resource.description} image={resource.image_url} path={path(`bookings/${resourceToken}`)} /> : null}
    <PublicLayout {...publicPageChrome(tenantSlug, displayName, path, bootstrap)} state={state}
      breadcrumb={[{ label: t`All resources`, href: path("bookings") }, { label: resource?.name ?? t`Resource` }]}>
      <PublicDetailLayout title={resource?.name ?? (state.status === "error" ? t`Resource unavailable` : t`Resource`)} state={state}
        cover={resource?.image_url ? { src: resource.image_url, alt: "" } : undefined}
        chips={resource ? [{ label: approval ? t`Needs approval` : t`Instant when available`, tone: approval ? "warn" : "success" }] : []}
        facts={resource?.location ? [{ identity: { kind: "icon", icon: "Info", tone: "neutral" }, primary: resource.location,
          secondary: resource.capacity ? `Capacity ${resource.capacity}` : "Capacity not specified" }] : []}
        sections={resource ? [
          ...photosSection(resource),
          { id: "about", label: t`About this resource`, content: <p className="whitespace-pre-wrap leading-7">{resource.description}</p> },
          { id: "rules", label: t`Booking rules`, content: <div className="grid gap-2 leading-7">
            <p>{t`${resource.rules.minimum_minutes}–${resource.rules.maximum_minutes} minutes; request at least ${resource.rules.lead_minutes} minutes ahead, up to ${resource.rules.advance_days} days ahead.`}</p>
            <p>{t`Changes and cancellation close ${resource.rules.cancellation_cutoff_hours} hours before the start. `}{approval ? t`Staff approval is required.` : t`Available times confirm immediately.`}</p>
          </div> },
          ...(resource.website ? [{ id: "details", label: t`Resource details`, content: <BookingResourceWebsite page={resource.website} slug={tenantSlug} /> }] : []),
          { id: "availability", label: t`Availability`, content: <AvailabilityCalendar makerspaceSlug={tenantSlug} publicToken={resource.public_token} /> },
        ] : []}
        actionCard={{ title: t`Choose a time`, state: "open",
          summary: resource ? <div className="flex flex-wrap items-end gap-6">
            <dl><dt className="eyebrow">{t`Capacity`}</dt><dd className="font-semibold tabular-nums text-ink">{resource.capacity || t`Not specified`}</dd></dl>
            {/* The flat per-booking price only; hourly rate cards and member discounts show in the quote once a time is chosen. */}
            {showPrice && Number(resource.payment_amount) > 0 ? <dl><dt className="eyebrow">{t`Price per booking`}</dt><dd className="font-semibold tabular-nums text-ink">{formatMoney(resource.payment_amount, resource.currency)}</dd></dl> : null}
          </div> : null,
          form: !resource ? null : session === "restoring" ? <p role="status" className="text-sm text-muted">{t`Restoring your session...`}</p>
            : session === "anonymous" ? <MemberAuthPanel embedded context={<p className="text-sm text-muted">{t`Sign in to submit a booking.`}</p>}
              makerspaceSlug={tenantSlug} onAuthenticated={() => setSession("authenticated")} />
            : <PublicBookingForm key={resourceToken} makerspaceSlug={tenantSlug} space={resource} showCalendar={false} />,
          note: approval ? t`Your request stays pending until makerspace staff review it.` : t`A non-overlapping slot is confirmed immediately.`,
          mobileBar: { summary: resource?.name ?? t`Resource`, label: t`Choose a time` } }} />
    </PublicLayout>
  </div>;
}
