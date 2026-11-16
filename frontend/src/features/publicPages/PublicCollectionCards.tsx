import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { RouteLink } from "../../components/ui/RouteLink";
import { EventPrice } from "../events/EventPrice";
import type { PublicEventCard, SpaceCard } from "./pageTypes";

export const safePublicLink = (value?: string | null) => {
  if (!value || /[\u0000-\u0020\u007f]/.test(value)) return undefined;
  try { const url = new URL(value, window.location.origin); return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? value : undefined; } catch { return undefined; }
};
export function PublicSpaceCards({ rows }: { rows: SpaceCard[] }) {
  return rows.length ? <ul className="grid gap-3 sm:grid-cols-2">{rows.map(row => <li key={row.slug} className="rounded-xl border border-line bg-panel p-4">
    {row.logo_url ? <img src={row.logo_url} alt="" width={48} height={48} className="mb-2 h-12 w-12 rounded-lg object-contain" /> : null}
    <h3 className="title-section"><RouteLink className="inline-flex min-h-11 items-center text-brand-ink underline" href={safePublicLink(row.canonical_url)}>{row.name}</RouteLink></h3>
  </li>)}</ul> : <p className="text-sm text-muted">{t`No public makerspaces to show.`}</p>;
}
/** `showPrice` false: the space's event charges are off (#184), so no price line. */
export function PublicEventCards({ rows, past = false, showPrice = true }: { rows: PublicEventCard[]; past?: boolean; showPrice?: boolean }) {
  return rows.length ? <ul className="grid gap-3">{rows.map((row, index) => <li key={`${row.starts_at}-${index}`} className="grid gap-2 rounded-xl border border-line bg-panel p-4">
    <h3 className="title-section">{!past && safePublicLink(row.event_url) ? <RouteLink className="inline-flex min-h-11 items-center text-brand-ink underline" href={row.event_url!}>{row.title}</RouteLink> : row.title}</h3>
    <p className="text-sm text-muted"><time dateTime={row.starts_at}>{new Date(row.starts_at).toLocaleString(formatLocale(), { timeZone: "timezone" in row ? row.timezone : undefined })}</time> – <time dateTime={row.ends_at}>{new Date(row.ends_at).toLocaleString(formatLocale(), { timeZone: "timezone" in row ? row.timezone : undefined })}</time></p>
    {"description" in row && row.description ? <p className="whitespace-pre-wrap text-sm">{row.description.slice(0, 300)}</p> : null}
    {!past && showPrice && "payment_amount" in row && row.payment_amount !== undefined && row.currency ? <dl className="text-sm"><EventPrice amount={row.payment_amount} currency={row.currency} /></dl> : null}
    {!past && "availability" in row && row.availability ? <p className="text-sm text-muted">{row.availability}</p> : null}
    {"host" in row && row.host ? <p className="text-sm">{t`Hosted by `}{"canonical_url" in row.host ? <RouteLink className="inline-flex min-h-11 items-center text-brand-ink underline" href={safePublicLink(row.host.canonical_url)}>{row.host.name}</RouteLink> : row.host.name}</p> : null}
  </li>)}</ul> : <p className="text-sm text-muted">{past ? t`No past events to show.` : t`No upcoming events. Check back soon.`}</p>;
}

