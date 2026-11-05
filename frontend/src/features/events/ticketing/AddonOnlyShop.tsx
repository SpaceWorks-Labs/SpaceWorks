import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ShoppingBag } from "lucide-react";

import { ErrorText } from "../../../components/ui";
import { StructuredApiError, tenantPublicRequest } from "../../../lib/api";
import type { PublicEventDetail } from "../eventTicketTypes";
import { shopError } from "./EventTicketShop";
import { OrderSummary } from "./OrderSummary";
import { basketRequest, emptyBasket, TicketShopPicker, type Basket } from "./TicketShopPicker";
import { fetchShop, placeOrder, policyLine, quoteOrder, ticketingKeys, type OrderQuote } from "./ticketingApi";

/**
 * Hack-money G9 (`events.accepted_addons`): on an event that reviews registrations, a person whose place is
 * CONFIRMED may buy add-ons alone (a T-shirt, meals, a hardware kit). The order sells no seat and names no
 * attendees; it reuses the L6 quote -> place-order -> checkout flow with an empty ticket list.
 */
export function AddonOnlyShop({ makerspaceSlug, makerspaceId, publicToken, ordersHref }: {
  makerspaceSlug: string; makerspaceId: number; publicToken: string; ordersHref: (orderId: number) => string;
}) {
  const [basket, setBasket] = useState<Basket>(emptyBasket);
  const [quote, setQuote] = useState<OrderQuote | null>(null);
  const event = useQuery({ queryKey: ["public-event", makerspaceSlug, publicToken], retry: false,
    queryFn: () => tenantPublicRequest<PublicEventDetail>(makerspaceSlug,
      `/public/${encodeURIComponent(makerspaceSlug)}/events/${encodeURIComponent(publicToken)}/`) });
  const approval = Boolean(event.data?.registration_requires_approval);
  const shopQuery = useQuery({ queryKey: ticketingKeys.shop(makerspaceSlug, publicToken), enabled: approval, retry: false,
    queryFn: () => fetchShop(makerspaceSlug, publicToken) });
  const shop = shopQuery.data;
  const eventId = shop?.event_id ?? 0;
  const body = () => ({ ...basketRequest(basket, []), tickets: [], buyer_attends: false, attendees: [] });
  const review = useMutation({ mutationFn: () => quoteOrder(makerspaceId, eventId, body()), onSuccess: setQuote });
  const pay = useMutation({
    mutationFn: () => placeOrder(makerspaceId, eventId, { ...body(), digest: quote?.quote.digest }),
    onSuccess: result => window.location.assign(result.checkout_url || ordersHref(result.order.id)),
    onError: error => { if (error instanceof StructuredApiError && error.code === "price_changed") setQuote(null); },
  });
  // Events without review sell add-ons with a ticket in the ordinary shop; nothing to add here.
  if (!approval || !shop || !shop.addons.length) return null;
  const chosen = (body().addons ?? []).length > 0;
  return <section className="grid gap-3 rounded-xl border border-line p-4" aria-labelledby="addon-only-title">
    <h2 id="addon-only-title" className="title-section flex items-center gap-2"><ShoppingBag className="text-accent" aria-hidden="true" />Add-ons for your place</h2>
    <p className="text-sm text-muted">Your place is confirmed. Add extras to it; you are not buying another seat.</p>
    <TicketShopPicker tickets={[]} addons={shop.addons} currency={shop.currency} orderMax={0} basket={basket}
      onChange={next => { setBasket(next); setQuote(null); }} />
    {!quote ? <p className="text-sm text-muted">{policyLine(shop.policy)}</p> : <OrderSummary quote={quote} />}
    {review.error || pay.error ? <ErrorText message={shopError(pay.error ?? review.error)} /> : null}
    {quote ? <button type="button" className="desk-button-brand w-full" disabled={pay.isPending} onClick={() => pay.mutate()}>
      {pay.isPending ? "Placing order…" : Number(quote.quote.total) > 0 ? "Continue to payment" : "Confirm order"}</button>
      : <button type="button" className="desk-button-brand w-full" disabled={!chosen || review.isPending} onClick={() => review.mutate()}>
        {review.isPending ? "Pricing…" : "Review add-ons"}</button>}
  </section>;
}
