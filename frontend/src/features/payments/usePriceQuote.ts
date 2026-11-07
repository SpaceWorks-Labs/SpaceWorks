import { formatLocale } from "../../lib/format";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import type { PricingPublicQuote, PricingQuoteRequest } from "../../generated/api";
import { tenantPublicRequest } from "../../lib/api";
import { useDebouncedValue } from "../../lib/useDebouncedValue";

export type { PricingPublicQuote, PricingQuoteRequest };

/** A quote is only worth asking for once the host has the thing being priced. */
export function quoteReady(request: PricingQuoteRequest) {
  switch (request.domain) {
    case "loans": return Boolean(request.request_id || request.items?.length);
    case "bookings": return Boolean((request.space_id || request.space_token) && request.starts_at && request.ends_at);
    case "machines": return Boolean(request.machine_id || request.machine_type_id);
    case "events": return Boolean(request.event_id || request.event_token);
    default: return true;
  }
}

/**
 * The live price preview (`POST public/{slug}/pricing/quote`). Input changes are debounced, the
 * previous quote stays on screen while the next one loads, and a 4xx is never retried -- 404 means
 * price lists are off or the thing is not public, 429 means the per-visitor throttle tripped.
 * Signed-in members get their own price: the shared public client sends the member session.
 * `enabled` false (the domain's charges are off, #184) never asks: the server would answer 404.
 */
export function usePriceQuote(slug: string, request: PricingQuoteRequest, delay = 400, enabled = true) {
  const body = useDebouncedValue(JSON.stringify(request), delay);
  const ready = enabled && Boolean(slug) && quoteReady(JSON.parse(body) as PricingQuoteRequest) && quoteReady(request);
  const query = useQuery({
    queryKey: ["pricing-quote", slug, body],
    queryFn: () => tenantPublicRequest<PricingPublicQuote>(slug, `/public/${encodeURIComponent(slug)}/pricing/quote`, {
      method: "POST", body,
    }),
    enabled: ready,
    retry: false,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
  return { ...query, ready };
}

export function quoteErrorStatus(error: unknown) {
  return error && typeof error === "object" ? (error as { status?: number }).status : undefined;
}

export function money(amount: string | number, currency: string) {
  try {
    return new Intl.NumberFormat(formatLocale(), { style: "currency", currency: currency.toUpperCase() }).format(Number(amount));
  } catch {
    return `${currency.toUpperCase()} ${amount}`;
  }
}

/** A `datetime-local` value as ISO, or undefined while it is blank or incomplete. */
export function isoTime(value: string) {
  const date = value ? new Date(value) : null;
  return date && !Number.isNaN(date.getTime()) ? date.toISOString() : undefined;
}

/** "1.0000" -> "1", "2.5000" -> "2.5" */
export const quantityText = (quantity: string) => String(Number(quantity));
