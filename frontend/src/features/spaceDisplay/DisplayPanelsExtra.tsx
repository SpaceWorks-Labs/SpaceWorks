import { t } from "@lingui/core/macro";
import type { InventoryHighlightsData, SponsorsWallData } from "./api";

const heading = "mb-6 text-4xl font-semibold text-ink";

type Availability = InventoryHighlightsData["items"][number]["availability"];

/** The same words the public catalogue shows: an exact count only when the item allows it, else a status. */
const availabilityText = (availability: Availability): string => {
  if (!availability) return "";
  return availability.mode === "exact_count" && typeof availability.count === "number"
    ? t`${availability.count} available` : availability.label;
};

/** A few public catalogue items with their public availability. Never locations, boxes or hidden counts. */
export function InventoryHighlightsPanel({ data }: { data: InventoryHighlightsData }) {
  return <section aria-labelledby="tv-inventory" className="grid gap-6">
    <h2 id="tv-inventory" className={heading}>{t`On the shelf`}</h2>
    <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {data.items.map((item) => <li key={item.name} className="flex min-w-0 flex-col gap-3 rounded-xl border border-line bg-panel p-5">
        {item.image_url ? <img src={item.image_url} alt="" loading="lazy" className="h-40 w-full rounded-lg object-cover" /> : null}
        <span className="break-words text-3xl font-semibold text-ink">{item.name}</span>
        {item.category ? <span className="text-xl text-muted">{item.category}</span> : null}
        {item.availability ? <span className="text-2xl tabular-nums text-ink">{availabilityText(item.availability)}</span> : null}
      </li>)}
    </ul>
  </section>;
}

/** The space's public sponsor wall: logos where there is one, the name where there is not. */
export function SponsorsPanel({ data }: { data: SponsorsWallData }) {
  return <section aria-labelledby="tv-sponsors" className="grid gap-6">
    <h2 id="tv-sponsors" className={heading}>{t`Thank you to our sponsors`}</h2>
    <ul className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
      {data.sponsors.map((sponsor) => <li key={sponsor.name} className="flex min-h-32 min-w-0 flex-col items-center justify-center gap-2 rounded-xl border border-line bg-panel p-5 text-center">
        {sponsor.logo_url ? <img src={sponsor.logo_url} alt={sponsor.name} loading="lazy" className="max-h-28 max-w-full object-contain" />
          : <span className="break-words text-3xl font-semibold text-ink">{sponsor.name}</span>}
        {sponsor.tier ? <span className="text-xl text-muted">{sponsor.tier}</span> : null}
      </li>)}
    </ul>
  </section>;
}
