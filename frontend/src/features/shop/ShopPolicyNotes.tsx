import type { ShopSummary } from "./shopApi";

/** What a buyer agrees to, shown before any payment step: pickup, holds, returns and the space's own policy. */
export function ShopPolicyNotes({ shop }: { shop: ShopSummary }) {
  const hold = shop.hold_minutes ? shop.hold_minutes >= 120
    ? `${Math.round(shop.hold_minutes / 60)} hours` : `${shop.hold_minutes} minutes` : "";
  return <section aria-label="Before you order" className="grid gap-2 rounded-xl border border-line p-4 text-sm leading-6">
    <h3 className="title-section">Before you order</h3>
    <p>Orders are collected in person{shop.pickup_events.length ? ", at the space or at one of its events" : " at the space"}.
      {shop.pay_online ? " You can pay online now or at the desk." : " You pay at the desk when you collect."}</p>
    {shop.pickup_note ? <p className="whitespace-pre-wrap">{shop.pickup_note}</p> : null}
    {hold ? <p>We keep your items aside for {hold} while you pay.</p> : null}
    {shop.returns_days > 0 ? <p>Returns are accepted at the desk within {shop.returns_days} days of collection.</p> : null}
    {shop.policy_text ? <p className="whitespace-pre-wrap text-muted">{shop.policy_text}</p> : null}
  </section>;
}
