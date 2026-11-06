import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ErrorText } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { OrderSummary } from "./OrderSummary";
import { basketRequest, emptyBasket, TicketShopPicker, type Basket } from "./TicketShopPicker";
import {
  fetchShop, placeOrder, policyLine, quoteOrder, ticketingKeys, unlockShop, type OrderQuote, type TicketShop,
} from "./ticketingApi";

const MESSAGES: Record<string, string> = {
  sold_out: "Not enough places are left for that choice.",
  order_limit: "That quantity is not allowed for this ticket.",
  amount_below_minimum: "That amount is below the minimum for this ticket.",
  access_code_invalid: "That access code is not valid for this event.",
  already_registered: "You already have a place here. Untick “One of these is for me” to buy for others.",
  price_changed: "The price changed. Review the new total before paying.",
  order_not_payable: "This event does not take ticket orders.",
  addon_unavailable: "One of the add-ons is not available.",
};

export function shopError(error: unknown) {
  if (!(error instanceof StructuredApiError)) return error ? "Something went wrong. Try again." : "";
  if (error.status === 401) return "Sign in to buy tickets.";
  return (error.code && MESSAGES[error.code]) || error.detail || error.message;
}

const emails = (text: string) => text.split(/[\s,;]+/).map(value => value.trim()).filter(Boolean);

/** G27-G30: choose tickets and add-ons, review the priced order with its policy, then pay. */
export function EventTicketShop({ makerspaceSlug, makerspaceId, publicToken, ordersHref, free = false }: {
  makerspaceSlug: string; makerspaceId: number; publicToken: string; ordersHref: (orderId: number) => string;
  /** #184: event charges are off here, so the same shop runs with no prices and settles free. */
  free?: boolean;
}) {
  const [basket, setBasket] = useState<Basket>(emptyBasket);
  const [codes, setCodes] = useState("");
  const [promo, setPromo] = useState("");
  const [others, setOthers] = useState("");
  const [buyerAttends, setBuyerAttends] = useState(true);
  const [quote, setQuote] = useState<OrderQuote | null>(null);
  const [unlocked, setUnlocked] = useState<TicketShop | null>(null);
  const shopQuery = useQuery({ queryKey: ticketingKeys.shop(makerspaceSlug, publicToken),
    queryFn: () => fetchShop(makerspaceSlug, publicToken) });
  const shop = unlocked ?? shopQuery.data;
  const eventId = shop?.event_id ?? 0;
  const unlock = useMutation({ mutationFn: () => unlockShop(makerspaceSlug, publicToken, emails(codes)), onSuccess: setUnlocked });
  const body = () => shop ? { ...basketRequest(basket, shop.ticket_types), promo_code: promo || undefined,
    access_codes: emails(codes), buyer_attends: buyerAttends, attendees: emails(others) } : { tickets: [] };
  const review = useMutation({ mutationFn: () => quoteOrder(makerspaceId, eventId, body()), onSuccess: setQuote });
  const pay = useMutation({
    mutationFn: () => placeOrder(makerspaceId, eventId, { ...body(), digest: quote?.quote.digest }),
    onSuccess: result => window.location.assign(result.checkout_url || ordersHref(result.order.id)),
    onError: error => { if (error instanceof StructuredApiError && error.code === "price_changed") setQuote(null); },
  });
  if (shopQuery.isLoading) return <p role="status">Loading tickets…</p>;
  if (!shop) return <ErrorText message={shopError(shopQuery.error) || "Tickets are not available."} />;
  const chosen = basketRequest(basket, shop.ticket_types).tickets.length > 0;
  const change = (next: Basket) => { setBasket(next); setQuote(null); };
  return <div className="grid gap-4">
    <TicketShopPicker tickets={shop.ticket_types} addons={shop.addons} currency={shop.currency}
      orderMax={shop.max_tickets_per_order} basket={basket} onChange={change} free={free} />
    <details className="grid gap-2"><summary className="cursor-pointer text-sm font-semibold">Have a code?</summary>
      <label className="grid gap-1 text-sm">Access code
        <span className="flex gap-2"><input className="desk-input flex-1" value={codes} onChange={event => setCodes(event.target.value)} />
          <button type="button" className="desk-button" disabled={!codes.trim() || unlock.isPending} onClick={() => unlock.mutate()}>Unlock</button></span>
      </label>
      {shop.promo_codes_enabled && !free ? <label className="grid gap-1 text-sm">Promo code
        <input className="desk-input" value={promo} onChange={event => { setPromo(event.target.value); setQuote(null); }} /></label> : null}
      {unlock.error ? <ErrorText message={shopError(unlock.error)} /> : null}
    </details>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={buyerAttends}
      onChange={event => { setBuyerAttends(event.target.checked); setQuote(null); }} />One of these is for me</label>
    <label className="grid gap-1 text-sm">Emails of the other people (optional; you can add them later)
      <textarea className="desk-input" rows={2} value={others} onChange={event => { setOthers(event.target.value); setQuote(null); }} /></label>
    {!quote ? <p className="text-sm text-muted">{policyLine(shop.policy)}</p> : <OrderSummary quote={quote} />}
    {review.error || pay.error ? <ErrorText message={shopError(pay.error ?? review.error)} /> : null}
    {quote ? <button type="button" className="desk-button-brand w-full" disabled={pay.isPending} onClick={() => pay.mutate()}>
      {pay.isPending ? "Placing order…" : Number(quote.quote.total) > 0 ? "Continue to payment" : "Confirm order"}</button>
      : <button type="button" className="desk-button-brand w-full" disabled={!chosen || review.isPending} onClick={() => review.mutate()}>
        {review.isPending ? "Pricing…" : "Review order"}</button>}
  </div>;
}
