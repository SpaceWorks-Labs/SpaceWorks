import { t } from "@lingui/core/macro";
import { useOptionalTenant } from "../../../lib/tenant";
import { PageHelp } from "../../help/PageHelp";
import { useTenantBootstrap } from "../../inventory/usePublicInventory";
import { MemberCalendarActions } from "../MemberCalendarActions";
import { bookingFeed, personalFeed, publicEventsFeedUrl } from "./calendarFeedsApi";
import { CalendarFeedLink } from "./CalendarFeedLink";

/** The space's switches, from the tenant bootstrap (the single-tenant one, or fetched by slug). */
export function useSpaceSwitches(slug: string) {
  const tenant = useOptionalTenant();
  const single = tenant?.mode === "single";
  const fetched = useTenantBootstrap(slug, !single);
  const bootstrap = single ? tenant?.bootstrap : fetched.data;
  const features = new Set(bootstrap?.features ?? []);
  const modules = new Set(bootstrap?.modules ?? []);
  const on = (key: string, module?: string) => features.has(key) && (!module || modules.has(module));
  return Object.assign(on, { known: Boolean(bootstrap) });
}

/**
 * Every calendar a person can subscribe to here, each behind its own switch: their events and
 * bookings, their volunteer and mentor shifts, one combined link, and the public events calendar.
 */
export function MemberCalendarLinks({ makerspaceId, makerspaceSlug }: { makerspaceId: number; makerspaceSlug: string }) {
  const on = useSpaceSwitches(makerspaceSlug);
  const publicFeed = on("events.public_feed", "events");
  return <div className="mt-3 grid gap-3" aria-label={t`Calendar links`}>
    <PageHelp article="member/calendar-links" topic="calendar links" slug={makerspaceSlug} />
    {/* Before the switches are known, keep today's event calendar (the server still answers 404 when off). */}
    {!on.known || on("events.calendar_feed", "events") ? <MemberCalendarActions makerspaceId={makerspaceId} makerspaceSlug={makerspaceSlug} /> : null}
    {on("bookings.calendar_feed", "bookings") ? <CalendarFeedLink title={t`My bookings calendar`} description={t`your bookings`}
      endpoint={bookingFeed(makerspaceSlug)} /> : null}
    {on("events.shifts_feed", "events") ? <CalendarFeedLink title={t`My shifts calendar`}
      description={t`your approved volunteer and mentor shifts`} endpoint={personalFeed(makerspaceId, "shifts")} /> : null}
    {on("calendar.combined_feed") ? <CalendarFeedLink title={t`Everything in one calendar`}
      description={t`your bookings, event registrations and shifts`} endpoint={personalFeed(makerspaceId, "combined")} /> : null}
    {publicFeed ? <div className="rounded-md border border-line p-3 text-sm">
      <p className="font-semibold text-ink">{t`Public events calendar`}</p>
      <p className="text-xs text-muted">{t`Everyone can subscribe to this space's listed events.`}</p>
      <input className="desk-input code-text mt-2 w-full" readOnly value={publicEventsFeedUrl(makerspaceSlug)}
        aria-label={t`Public events calendar link`} onFocus={event => event.currentTarget.select()} />
    </div> : null}
  </div>;
}
