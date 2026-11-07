import { t } from "@lingui/core/macro";
import { RouteLink } from "../../components/ui/RouteLink";

/** Owner history destinations; the core money ledger never depends on membership or the rail. */
export function MemberHistoryLinks({ slug, modules = [], features = [] }: { slug: string; modules?: string[]; features?: string[] }) {
  const base = `${slug ? `/m/${slug}` : ""}/member`;
  const links = [
    ...(modules.includes("request_workflow") && features.includes("loans.enabled") ? [{ label: t`Borrowing history`, href: `${base}/loans/history` }] : []),
    ...(modules.includes("events") ? [{ label: t`Event history`, href: `${base}/events/history` }] : []),
    ...(modules.includes("bookings") ? [{ label: t`Booking history`, href: `${base}/bookings?period=past` }] : []),
    ...(modules.includes("shop") ? [{ label: t`Shop orders`, href: `${base}/shop-orders` }] : []),
    { label: t`Payments & receipts`, href: `${base}/payments` },
  ];
  return <section className="desk-panel grid gap-3 p-4 sm:p-5" aria-labelledby="own-history-heading">
    <h2 className="title-panel" id="own-history-heading">{t`Your history`}</h2>
    <p className="text-sm text-muted">{t`Open your own activity, orders, payments and receipts in this space.`}</p>
    <nav aria-label={t`Your activity history`} className="flex flex-wrap gap-3">{links.map(link =>
      <RouteLink key={link.href} className="desk-button" href={link.href}>{link.label}</RouteLink>)}</nav>
  </section>;
}
