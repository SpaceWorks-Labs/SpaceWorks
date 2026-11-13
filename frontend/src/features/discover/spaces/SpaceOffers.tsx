import { t } from "@lingui/core/macro";
import { BadgeCheck, Boxes, CalendarClock, CalendarDays, Cog, HandHeart, Store, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { formatDate, formatTime } from "../../../lib/format";
import type { PublicNextEvent, PublicSpaceOffer } from "../../../types/inventory";

// A function, not a constant: the labels follow a language switch.
const OFFERS = (): Record<PublicSpaceOffer, { label: string; icon: LucideIcon }> => ({
  inventory: { label: t`Tool loans`, icon: Boxes },
  machines: { label: t`Machines`, icon: Cog },
  events: { label: t`Events`, icon: CalendarDays },
  bookings: { label: t`Room bookings`, icon: CalendarClock },
  shop: { label: t`Shop`, icon: Store },
  memberships: { label: t`Memberships`, icon: BadgeCheck },
  donations: { label: t`Donations`, icon: HandHeart },
});

/** What the space offers, as quiet labelled chips in the server's order; an unknown key is skipped, never shown raw. */
export function SpaceOfferChips({ offers }: { offers?: readonly string[] }) {
  const labels = OFFERS();
  const known = (offers ?? []).filter((offer): offer is PublicSpaceOffer => offer in labels);
  if (!known.length) return null;
  return <ul className="sw-space-offers" aria-label={t`What this space offers`}>
    {known.map(offer => {
      const { label, icon: Icon } = labels[offer];
      return <li key={offer} className="sw-space-offer"><Icon aria-hidden="true" size={14} strokeWidth={2.25} />{label}</li>;
    })}
  </ul>;
}

/** The space's next public event: a link of its own, above the card's whole-card link. */
export function SpaceNextEvent({ event }: { event?: PublicNextEvent | null }) {
  // Only an in-app path: a protocol-relative `//host` would leave the site.
  if (!event?.title || !/^\/(?!\/)/.test(event.public_url ?? "")) return null;
  const when = `${formatDate(event.starts_at, { weekday: "short", day: "numeric", month: "short" })} · ${formatTime(event.starts_at)}`;
  return <p className="sw-space-event">
    <CalendarDays aria-hidden="true" size={16} className="mt-0.5 shrink-0" />
    <span className="grid min-w-0 gap-0.5">
      <span className="sw-space-event-label">{t`Next event`} · <time dateTime={event.starts_at}>{when}</time></span>
      <Link className="sw-space-event-link" to={event.public_url}>{event.title}</Link>
    </span>
  </p>;
}
