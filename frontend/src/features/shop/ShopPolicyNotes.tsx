import { t } from "@lingui/core/macro";
import type { ShopSummary } from "./shopApi";

/** What a buyer agrees to, shown before any payment step: pickup, holds, returns and the space's own policy. */
export function ShopPolicyNotes({ shop }: { shop: ShopSummary }) {
  const hold = shop.hold_minutes ? shop.hold_minutes >= 120
    ? `${Math.round(shop.hold_minutes / 60)} hours` : `${shop.hold_minutes} minutes` : "";
  return <section aria-label={t`Before you order`} className="grid gap-2 rounded-xl border border-line p-4 text-sm leading-6">
    <h3 className="title-section">{t`Before you order`}</h3>
    <p>{t`Orders are collected in person`}{shop.pickup_events.length ? t`, at the space or at one of its events` : t` at the space`}.
      {shop.pay_online ? t` You can pay online now or at the desk.` : t` You pay at the desk when you collect.`}</p>
    {shop.pickup_note ? <p className="whitespace-pre-wrap">{shop.pickup_note}</p> : null}
    {hold ? <p>{t`We keep your items aside for ${hold} while you pay.`}</p> : null}
    {shop.returns_days > 0 ? <p>{t`Returns are accepted at the desk within ${shop.returns_days} days of payment.`}</p> : null}
    {shop.policy_text ? <p className="whitespace-pre-wrap text-muted">{shop.policy_text}</p> : null}
  </section>;
}
