import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { StructuredApiError } from "../../lib/api";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { emptyGuest, GuestIdentityFields, guestReady, type GuestIdentity } from "./GuestIdentityFields";
import {
  changedQuote, placeShopOrder, quoteCart, shopErrorMessage, shopKeys, type OrderRequest, type ShopQuote, type ShopSummary,
} from "./shopApi";
import { ShopOrderPlaced, type Placed } from "./ShopOrderPlaced";
import { ShopPolicyNotes } from "./ShopPolicyNotes";
import { forgetPickupEvent, initialPickup } from "./pickupPreference";
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
  // #135 Q-S18: an event page's merch link opens the checkout with that event's pickup chosen.
  const [start] = useState(() => initialPickup(slug, shop.pickup_events));
  const [pickup, setPickup] = useState<"space" | number>(start.pickup);
  const pickupEvents = start.extra ? [...shop.pickup_events, start.extra] : shop.pickup_events;
  const signature = JSON.stringify(request);
  const [changedState, setChangedState] = useState<{ signature: string; quote: ShopQuote } | null>(null);
  const changed = changedState?.signature === signature ? changedState.quote : null;
  const setChanged = (next: ShopQuote | null) => setChangedState(next ? { signature, quote: next } : null);
  const [placed, setPlaced] = useState<Placed | null>(null);
  const quoteQuery = useQuery({ queryKey: shopKeys.quote(slug, signedIn, request), enabled: request.length > 0 && session !== "restoring" && !placed,
    queryFn: () => quoteCart(slug, request, signedIn), retry: false });
  const quote = changed ?? quoteQuery.data;
  const labelFor = (variantId: number) => lines.find(line => line.variantId === variantId)?.label ?? "";
  // SH-3: one Idempotency-Key per checkout attempt (same basket, pickup and buyer). A double submit or a retry after a
  // lost response reuses it, so the server hands back the first order instead of charging twice. A new attempt gets a new key.
  const attempt = useRef<{ signature: string; key: string } | null>(null);
  const inFlight = useRef(false); // a second click lands before the re-render that disables the button
  const attemptKey = () => {
    const current = JSON.stringify([signature, pickup, signedIn, signedIn ? "" : guest.email.trim().toLowerCase()]);
    if (attempt.current?.signature !== current) attempt.current = { signature: current, key: crypto.randomUUID() };
    return attempt.current.key;
  };
  const place = useMutation({
    mutationFn: () => {
      const body: OrderRequest = { lines: request, quote_digest: quote?.digest, pickup_at: pickup === "space" ? "space" : "event",
        ...(pickup === "space" ? {} : { pickup_event_id: pickup }),
        ...(signedIn ? {} : { guest_name: guest.name.trim(), guest_email: guest.email.trim(), email_code: guest.code.trim() }) };
      return placeShopOrder(slug, body, signedIn, attemptKey());
    },
    onSuccess: result => {
      attempt.current = null;
      forgetPickupEvent(slug);
      onPlaced();
      if (result.checkout_url) window.location.assign(result.checkout_url);
      else setPlaced({ ...result, signedIn });
    },
    onSettled: () => { inFlight.current = false; },
    onError: error => {
      // The server answered and refused (4xx): nothing was placed, so the next try is a new attempt. A network error or a 5xx
      // may have placed the order, so the key is kept for the retry.
      if (error instanceof StructuredApiError && error.status < 500) attempt.current = null;
      const next = changedQuote(error); if (next) setChanged(next);
    },
  });
  if (placed) return <ShopOrderPlaced placed={placed} path={path} />;
  if (!lines.length) return null;
  if (session === "restoring") return <p role="status" className="text-sm text-muted">{t`Checking your sign-in…`}</p>;
  const needsAccount = !signedIn && (!shop.guest_checkout || signIn);
  const ready = Boolean(quote) && !quoteQuery.isFetching && (signedIn || guestReady(guest));
  const due = Number(quote?.amount_due ?? 0) > 0;
  const payOnline = shop.pay_online && due;
  return <div className="grid gap-4">
    <ShopPolicyNotes shop={shop} />
    {pickupEvents.length ? <label className="grid gap-1 text-sm font-semibold text-ink">{t`Where will you collect it?`}<select className="desk-input min-h-11 font-normal" value={String(pickup)} onChange={event => {
        setPickup(event.target.value === "space" ? "space" : Number(event.target.value));
      }}>
        <option value="space">{t`At ${shop.name}`}</option>
        {pickupEvents.map(event => <option key={event.id} value={event.id}>
          {t`At ${event.title} (${new Date(event.starts_at).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" })})`}</option>)}
      </select></label> : null}
    {quoteQuery.isLoading ? <p role="status" className="text-sm text-muted">{t`Pricing your basket…`}</p> : null}
    {quoteQuery.error ? <p role="alert" className="text-sm text-danger">{shopErrorMessage(quoteQuery.error, labelFor)}</p> : null}
    {changed ? <p role="alert" className="rounded-xl border border-line bg-surface p-3 text-sm text-ink">
      {t`Prices changed since you looked. This is the new total; confirm to place the order at this price.`}</p> : null}
    {quote ? <ShopQuoteSummary quote={quote} /> : null}
    {needsAccount ? <MemberAuthPanel embedded makerspaceSlug={slug}
      context={<p className="text-sm text-muted">{shop.guest_checkout ? t`Sign in to order with your account.` : t`Sign in to order from this shop.`}</p>}
      onAuthenticated={() => { setSignIn(false); setChanged(null); onSession("authenticated"); }} />
      : !signedIn ? <GuestIdentityFields slug={slug} value={guest} onChange={setGuest} onSignIn={() => setSignIn(true)} /> : null}
    {place.error && !changed ? <p role="alert" className="text-sm text-danger">{shopErrorMessage(place.error, labelFor)}</p> : null}
    {!needsAccount ? <button type="button" className="desk-button-brand min-h-11 w-full" disabled={!ready || place.isPending}
      onClick={() => { if (inFlight.current) return; inFlight.current = true; place.mutate(); }}>
      {place.isPending ? t`Placing your order…` : changed ? t`Confirm the new total` : payOnline ? t`Continue to payment` : due ? t`Place order, pay at the desk` : t`Place order`}
    </button> : null}
  </div>;
}
