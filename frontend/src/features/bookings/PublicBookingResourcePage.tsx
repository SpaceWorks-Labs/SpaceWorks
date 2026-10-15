import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PageMetadata } from "../../components/PageMetadata";
import { SkipLink } from "../../components/SkipLink";
import { ThemeToggle } from "../../components/ThemeToggle";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { getAccessToken, refreshAccessToken } from "../../lib/api";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { PublicBookingForm } from "./PublicBookingForm";
import { BookingResourceWebsite } from "./BookingResourceWebsite";
import { usePublicBookingResource } from "./bookingWebsiteApi";

export function PublicBookingResourcePage() {
  const { slug = "", resourceToken = "" } = useParams();
  const tenant = useTenant();
  const tenantSlug = tenant.mode === "single" ? tenant.slug : slug;
  const path = useTenantPath(tenantSlug);
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
  return <main className="desk-shell min-h-screen px-5 py-6"><SkipLink />
    <div className="mx-auto grid max-w-4xl gap-5" id="main-content">
      <nav className="flex items-center justify-between"><Link className="desk-button" to={path("bookings")}>All resources</Link><ThemeToggle /></nav>
      {query.isLoading ? <p role="status">Loading resource…</p> : null}
      {!valid || query.error ? <div role="alert"><h1 className="title-page">Resource unavailable</h1><p>This resource may be private or no longer available.</p>{valid ? <button className="desk-button" onClick={() => query.refetch()}>Retry</button> : null}</div> : null}
      {resource ? <>
        <PageMetadata title={resource.name} description={resource.description} image={resource.image_url} path={path(`bookings/${resourceToken}`)} />
        <h1 className="title-page">{resource.name}</h1>
        {resource.image_url ? <img className="max-h-80 w-full rounded-xl object-cover" src={resource.image_url} alt="" /> : null}
        <p className="whitespace-pre-wrap">{resource.description}</p><p>{resource.location}</p>
        <dl className="flex flex-wrap gap-5 text-sm"><div><dt>Capacity</dt><dd>{resource.capacity || "Not specified"}</dd></div><div><dt>Flat price</dt><dd>{resource.payment_amount} {resource.currency.toUpperCase()}</dd></div></dl>
        <section className="desk-panel p-5"><h2 className="title-section">Booking rules</h2>
          <p>{resource.rules.minimum_minutes}–{resource.rules.maximum_minutes} minutes; request at least {resource.rules.lead_minutes} minutes ahead, up to {resource.rules.advance_days} days ahead.</p>
          <p>Changes and cancellation close {resource.rules.cancellation_cutoff_hours} hours before the start. {resource.approval_mode === "approve" ? "Staff approval is required." : "Available times confirm immediately."}</p>
        </section>
        {resource.website ? <BookingResourceWebsite page={resource.website} slug={tenantSlug} /> : null}
        <section className="desk-panel p-5"><h2 className="title-section">Choose a time</h2>
          {session === "restoring" ? <p role="status">Restoring your session...</p> : session === "anonymous" ? <>
            <p>Sign in to submit a booking.</p>
            <MemberAuthPanel makerspaceSlug={tenantSlug} onAuthenticated={() => setSession("authenticated")} />
          </> : <PublicBookingForm key={resourceToken} makerspaceSlug={tenantSlug} space={resource} />}
        </section>
      </> : null}
    </div>
  </main>;
}
