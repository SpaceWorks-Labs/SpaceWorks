import { t } from "@lingui/core/macro";

import { RouteLink } from "../../components/ui/RouteLink";
import { eventOffersEnabled, useEventShopOffers, type EventShopOffers as Offers } from "./eventOffersApi";
import { PICKUP_EVENT_PARAM, rememberPickupEvent } from "./pickupPreference";
import { priceRange } from "./shopApi";

type Bootstrap = Parameters<typeof eventOffersEnabled>[0];

const pickupHref = (path: (part?: string) => string, part: string, eventId: number) =>
  `${path(part)}?${PICKUP_EVENT_PARAM}=${eventId}`;

/**
 * #135 Q-S18 follow-up: the shop items an event offers, each linking into the normal shop
 * with this event chosen for pickup. A purchase is its own shop order, never part of the
 * registration. `selling` false (shop charges off, #184) hides prices.
 */
export function EventShopOfferList({ offers, slug, path, selling }: {
  offers: Offers; slug: string; path: (part?: string) => string; selling: boolean;
}) {
  const remember = () => rememberPickupEvent(slug, offers.event);
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`Order online and collect it at this event. Shop orders are paid separately from registration.`}</p>
    <ul className="grid gap-3 sm:grid-cols-2">
      {offers.products.map(product => <li key={product.id} className="flex min-w-0 items-center gap-3 rounded-xl border border-line bg-panel p-3">
        {product.image_url ? <img src={product.image_url} alt="" loading="lazy" className="h-16 w-16 shrink-0 rounded-lg object-cover" /> : null}
        <div className="grid min-w-0 gap-1">
          <RouteLink href={pickupHref(path, `shop/${product.slug}`, offers.event.id)} onClick={remember}
            className="break-words font-semibold text-ink underline-offset-4 hover:underline">{product.name}</RouteLink>
          {selling && product.price_from !== null ? <span className="text-sm tabular-nums text-muted">{priceRange(product, offers.currency)}</span> : null}
          {product.sold_out ? <span className="text-sm text-muted">{t`Sold out`}</span> : null}
        </div>
      </li>)}
    </ul>
  </div>;
}

/** A compact "Add merch" link for a registrant's ticket page; nothing when the event offers nothing. */
export function EventMerchLink({ slug, publicToken, bootstrap, path }: {
  slug: string; publicToken: string; bootstrap: Bootstrap; path: (part?: string) => string;
}) {
  const offers = useEventShopOffers(slug, publicToken, eventOffersEnabled(bootstrap));
  const data = offers.data;
  if (!data?.products.length) return null;
  return <RouteLink className="desk-button" href={pickupHref(path, "shop", data.event.id)}
    onClick={() => rememberPickupEvent(slug, data.event)}>{t`Add merch for pickup at this event`}</RouteLink>;
}
