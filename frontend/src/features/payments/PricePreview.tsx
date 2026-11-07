import { t } from "@lingui/core/macro";
import { useEffect, useId, useRef } from "react";
import { Receipt } from "lucide-react";

import { useChargesOn } from "../../lib/charges";
import { QuoteExtras, QuoteLines, QuoteTotals } from "./PricePreviewDetails";
import { quoteErrorStatus, usePriceQuote, type PricingPublicQuote, type PricingQuoteRequest } from "./usePriceQuote";

const isQuote = (value: unknown): value is PricingPublicQuote =>
  Boolean(value && typeof value === "object" && Array.isArray((value as PricingPublicQuote).quote?.lines));

/**
 * The member-facing price preview (lane L15). Hosts pass what is being priced; the quote follows
 * their inputs live. Renders nothing until there is something to price, while price lists are off
 * (404) or on any other refusal -- the price is advisory here, the submit re-checks it. `onDigest`
 * hands the quote's digest to a host that wants to send it with its submit (409 `price_changed`).
 * In a free domain (its charges off, #184) it neither fetches nor renders.
 */
export function PricePreview({ makerspaceSlug, request, onDigest, className = "" }: {
  makerspaceSlug: string; request: PricingQuoteRequest; onDigest?: (digest: string) => void; className?: string;
}) {
  const id = useId();
  const chargesOn = useChargesOn(request.domain, makerspaceSlug);
  const quote = usePriceQuote(makerspaceSlug, request, 400, chargesOn);
  const digestHandler = useRef(onDigest);
  digestHandler.current = onDigest;
  const data = isQuote(quote.data) ? quote.data : undefined;
  // A placeholder is the previous input's quote: never hand its digest to a submit.
  const digest = quote.ready && !quote.error && !quote.isPlaceholderData ? data?.digest : undefined;
  useEffect(() => { if (digest) digestHandler.current?.(digest); }, [digest]);

  if (!quote.ready) return null;
  if (quote.error) {
    return quoteErrorStatus(quote.error) === 429
      ? <p role="status" className={`text-sm text-muted ${className}`}>{t`Price preview unavailable right now`}</p> : null;
  }
  if (!data) return null;
  const free = Number(data.quote.total) <= 0 && !data.deposit;
  return <section aria-labelledby={id} aria-busy={quote.isFetching} className={`grid gap-3 rounded-xl border border-line bg-panel p-4 text-sm ${className}`}>
    <div className="flex items-center justify-between gap-2">
      <h3 id={id} className="title-section flex items-center gap-2"><Receipt aria-hidden="true" className="h-4 w-4 text-muted" />{t`Price`}</h3>
      {quote.isFetching ? <span className="text-xs text-muted">{t`Updating…`}</span> : null}
    </div>
    <div aria-live="polite" aria-atomic="true" className="grid gap-3">
      {free ? <p className="font-semibold text-ink">{t`Free`}</p> : <><QuoteLines data={data} /><QuoteTotals data={data} /></>}
      {free ? null : <QuoteExtras data={data} />}
    </div>
    {free && (data.policy || data.refund_summary) ? <QuoteExtras data={{ ...data, members_total: null }} /> : null}
  </section>;
}
