import { t } from "@lingui/core/macro";
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { money } from "./usePriceQuote";

type ChangedQuote = { currency?: unknown; total?: unknown; lines?: unknown };
type ChangedLine = { label?: unknown; net?: unknown };

const fields = (error: unknown) => (error && typeof error === "object" ? error as { status?: number; code?: string; body?: { quote?: ChangedQuote } } : {});

/** A submit refused with 409 `price_changed`: the price moved after the member saw it. */
export function isPriceChanged(error: unknown) {
  const { status, code } = fields(error);
  return status === 409 && code === "price_changed";
}

/**
 * Shows the new price from a 409 `price_changed` body and refreshes the live preview, so the
 * member's next submit carries the new digest. Only the string fields of the returned quote are
 * read (labels and amounts): the error body is serialized as error details, which stringifies
 * nulls, booleans and numbers.
 */
export function PriceChangedNotice({ makerspaceSlug, error }: { makerspaceSlug: string; error: unknown }) {
  const queryClient = useQueryClient();
  const changed = isPriceChanged(error);
  useEffect(() => {
    if (changed) void queryClient.invalidateQueries({ queryKey: ["pricing-quote", makerspaceSlug] });
  }, [changed, error, makerspaceSlug, queryClient]);
  if (!changed) return null;
  const quote = fields(error).body?.quote ?? {};
  const currency = typeof quote.currency === "string" ? quote.currency : "";
  const lines = (Array.isArray(quote.lines) ? quote.lines : []) as ChangedLine[];
  return <div role="alert" className="grid gap-2 rounded-lg border border-warn bg-warn-soft p-3 text-sm">
    <p className="font-semibold text-ink">{t`The price changed — please check and confirm again.`}</p>
    {currency && lines.length ? <ul className="grid gap-1">{lines.map((line, index) => typeof line.label === "string" && typeof line.net === "string"
      ? <li key={index} className="flex justify-between gap-3"><span>{line.label}</span><span className="tabular-nums">{money(line.net, currency)}</span></li> : null)}</ul> : null}
    {currency && typeof quote.total === "string"
      ? <p className="flex justify-between gap-3 font-semibold text-ink"><span>{t`New total`}</span><span className="tabular-nums">{money(quote.total, currency)}</span></p> : null}
  </div>;
}
