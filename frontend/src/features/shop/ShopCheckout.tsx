import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { emptyGuest, GuestIdentityFields, guestReady, type GuestIdentity } from "./GuestIdentityFields";
import {
  changedQuote, placeShopOrder, quoteCart, shopErrorMessage, shopKeys, type OrderRequest, type ShopQuote, type ShopSummary,
} from "./shopApi";
import { ShopOrderPlaced, type Placed } from "./ShopOrderPlaced";
import { ShopPolicyNotes } from "./ShopPolicyNotes";
import { ShopQuoteSummary } from "./ShopQuoteSummary";
import { cartRequest, type CartLine } from "./useShopCart";
import type { MemberSession } from "./useShopSpace";

/** Review and place: policy first, the server's quote, who is buying, then pay online or at the desk. No effects here. */
export function ShopCheckout({ slug, shop, lines, session, onSession, onPlaced, path }: {
  slug: string; shop: ShopSummary; lines: CartLine[]; session: MemberSession; onSession: (next: MemberSession) => void;
  onPlaced: () => void; path: (part?: string) => string;
}) {
  const signedIn = session === "authenticated";
  const request = cartRequest(lines);
  const [guest, setGuest] = useState<GuestIdentity>(emptyGuest);
  const [signIn, setSignIn] = useState(false);
  const [pickup, setPickup] = useState<"space" | number>("space");
  const signature = JSON.stringify(request);
  const [changedState, setChangedState] = useState<{ signature: string; quote: ShopQuote } | null>(null);
  const changed = changedState?.signature === signature ? changedState.quote : null;
  const setChanged = (next: ShopQuote | null) => setChangedState(next ? { signature, quote: next } : null);
  const [placed, setPlaced] = useState<Placed | null>(null);
  const quoteQuery = useQuery({ queryKey: shopKeys.quote(slug, signedIn, request), enabled: request.length > 0 && session !== "restoring" && !placed,
    queryFn: () => quoteCart(slug, request, signedIn), retry: false });
  const quote = changed ?? quoteQuery.data;
  const labelFor = (variantId: number) => lines.find(line => line.variantId === variantId)?.label ?? "";
  const place = useMutation({
    mutationFn: () => {
      const body: OrderRequest = { lines: request, quote_digest: quote?.digest, pickup_at: pickup === "space" ? "space" : "event",
        ...(pickup === "space" ? {} : { pickup_event_id: pickup }),
        ...(signedIn ? {} : { guest_name: guest.name.trim(), guest_email: guest.email.trim(), email_code: guest.code.trim() }) };
      return placeShopOrder(slug, body, signedIn);
    },
    onSuccess: result => {
      onPlaced();
      if (result.checkout_url) window.location.assign(result.checkout_url);
      else setPlaced({ ...result, signedIn });
    },
    onError: error => { const next = changedQuote(error); if (next) setChanged(next); },
  });
  if (placed) return <ShopOrderPlaced placed={placed} path={path} />;
  if (!lines.length) return null;
  if (session === "restoring") return <p role="status" className="text-sm text-muted">Checking your sign-in…</p>;
  const needsAccount = !signedIn && (!shop.guest_checkout || signIn);
  const ready = Boolean(quote) && !quoteQuery.isFetching && (signedIn || guestReady(guest));
  const due = Number(quote?.amount_due ?? 0) > 0;
  const payOnline = shop.pay_online && due;
  return <div className="grid gap-4">
    <ShopPolicyNotes shop={shop} />
    {shop.pickup_events.length ? <label className="grid gap-1 text-sm font-semibold text-ink">Where will you collect it?
      <select className="desk-input min-h-11 font-normal" value={String(pickup)} onChange={event => {
        setPickup(event.target.value === "space" ? "space" : Number(event.target.value));
      }}>
        <option value="space">At {shop.name}</option>
        {shop.pickup_events.map(event => <option key={event.id} value={event.id}>
          At {event.title} ({new Date(event.starts_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })})</option>)}
      </select></label> : null}
    {quoteQuery.isLoading ? <p role="status" className="text-sm text-muted">Pricing your basket…</p> : null}
    {quoteQuery.error ? <p role="alert" className="text-sm text-danger">{shopErrorMessage(quoteQuery.error, labelFor)}</p> : null}
    {changed ? <p role="alert" className="rounded-xl border border-line bg-surface p-3 text-sm text-ink">
      Prices changed since you looked. This is the new total; confirm to place the order at this price.</p> : null}
    {quote ? <ShopQuoteSummary quote={quote} /> : null}
    {needsAccount ? <MemberAuthPanel embedded makerspaceSlug={slug}
      context={<p className="text-sm text-muted">{shop.guest_checkout ? "Sign in to order with your account." : "Sign in to order from this shop."}</p>}
      onAuthenticated={() => { setSignIn(false); setChanged(null); onSession("authenticated"); }} />
      : !signedIn ? <GuestIdentityFields slug={slug} value={guest} onChange={setGuest} onSignIn={() => setSignIn(true)} /> : null}
    {place.error && !changed ? <p role="alert" className="text-sm text-danger">{shopErrorMessage(place.error, labelFor)}</p> : null}
    {!needsAccount ? <button type="button" className="desk-button-brand min-h-11 w-full" disabled={!ready || place.isPending}
      onClick={() => place.mutate()}>
      {place.isPending ? "Placing your order…" : changed ? "Confirm the new total" : payOnline ? "Continue to payment" : due ? "Place order, pay at the desk" : "Place order"}
    </button> : null}
  </div>;
}
