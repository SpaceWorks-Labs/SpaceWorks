import { t } from "@lingui/core/macro";
import { useState } from "react";

import type { ListLayoutProps } from "../../components/layouts";
import type { StaffAuthUser } from "../../lib/api";
// Lazy, so an account holding only event grants never downloads the booking console (and vice versa).
import { GrantedBookingSpacesPanel, GrantedEventsPanel } from "./StaffTabLoaders";

/** The page frame a granted list adopts when it shares the Assigned resources page with the other kind. */
export type GrantedListFrame = Pick<ListLayoutProps, "header" | "tabs" | "activeTab" | "onTabChange">;

/**
 * Assigned resources owns one page heading. An account holding only one kind of grant sees that list as
 * the page; holding both, the two lists become tabs under a single heading instead of two stacked pages.
 */
export function GrantedResourcesPanel({ eventGrants, bookingGrants, makerspaceId }: {
  eventGrants?: StaffAuthUser["event_grants"];
  bookingGrants: boolean;
  makerspaceId?: number;
}) {
  const [tab, setTab] = useState("events");
  const events = Boolean(eventGrants?.length);
  if (!events || !bookingGrants) return events
    ? <GrantedEventsPanel grants={eventGrants} makerspaceId={makerspaceId} />
    : <GrantedBookingSpacesPanel makerspaceId={makerspaceId} />;
  const frame: GrantedListFrame = {
    header: { title: t`Assigned resources`, subtitle: t`Open an event or a booking resource to use your assigned permissions.` },
    tabs: [{ key: "events", label: t`Events` }, { key: "bookings", label: t`Booking resources` }],
    activeTab: tab, onTabChange: setTab,
  };
  return tab === "bookings"
    ? <GrantedBookingSpacesPanel makerspaceId={makerspaceId} frame={frame} />
    : <GrantedEventsPanel grants={eventGrants} makerspaceId={makerspaceId} frame={frame} />;
}
