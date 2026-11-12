import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";

import { Callout, ConfirmDialog } from "../../components/ui";
import { money } from "../payments/usePriceQuote";
import { approveQuote, changedQuote, declineQuote, jobErrorMessage } from "./api";
import type { JobQuote, MemberJob } from "./types";
import { BoxArt } from "../../components/BoxSpinner";

function QuoteLines({ quote }: { quote: JobQuote }) {
  return <dl className="grid gap-2 text-sm">
    {quote.lines.map((line, index) => <div key={`${line.label}-${index}`} className="flex justify-between gap-4">
      <dt className="min-w-0 break-words text-muted">{line.label}</dt><dd className="tabular-nums text-ink">{money(line.net, quote.currency)}</dd></div>)}
    <div className="flex justify-between gap-4 border-t border-line pt-2 font-semibold">
      <dt>{t`Total`}</dt><dd className="tabular-nums">{money(quote.total, quote.currency)}</dd></div>
  </dl>;
}

/**
 * The quote the member answers. Approve sends the digest of the price they were shown; if staff
 * changed it meanwhile the server refuses (409 price_changed) with the new quote, which replaces
 * the old one here so the member approves what they actually saw.
 */
export function JobQuoteCard({ job, paymentsHref, onUpdated }: { job: MemberJob; paymentsHref: string; onUpdated: (job: MemberJob) => void }) {
  const [shown, setShown] = useState<JobQuote | null>(null);
  const [declining, setDeclining] = useState(false);
  const quote = shown ?? job.quote;
  const approve = useMutation({ mutationFn: (digest: string) => approveQuote(job.id, digest),
    onSuccess: next => { setShown(null); onUpdated(next); },
    onError: error => { const fresh = changedQuote(error); if (fresh) setShown(fresh); } });
  const decline = useMutation({ mutationFn: () => declineQuote(job.id), onSuccess: next => { setDeclining(false); onUpdated(next); } });
  if (job.awaiting_payment) return <section className="desk-panel grid gap-3 p-5" aria-labelledby="job-quote-title">
    <h2 id="job-quote-title" className="title-panel">{t`Awaiting payment`}</h2>
    <p className="text-sm text-muted">{t`You approved the quote. Your job joins the queue once it is paid.`}</p>
    {quote ? <QuoteLines quote={quote} /> : null}
    <Link className="desk-button-brand justify-self-start" to={paymentsHref}>{t`Pay now`}</Link>
  </section>;
  if (job.label !== "quote_sent" || !quote) return null;
  const priceChanged = Boolean(shown);
  const expired = job.quote_expires_at ? new Date(job.quote_expires_at).getTime() <= Date.now() : false;
  return <section className="desk-panel grid gap-4 p-5" aria-labelledby="job-quote-title">
    <div><h2 id="job-quote-title" className="title-panel">{t`Your quote`}</h2>
      <p className="mt-1 text-sm text-muted">{t`Approve it and your job joins the queue`}{job.quote_expires_at ? <> · {expired ? "expired" : t`valid until`} <time dateTime={job.quote_expires_at}>
        {new Date(job.quote_expires_at).toLocaleString(formatLocale(), { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</time></> : null}.</p></div>
    {priceChanged ? <div role="alert"><Callout size="inline" tone="warn" lead="The price changed since you opened this page." body={t`Check the new quote below and approve it again if it suits you.`} /></div> : null}
    <QuoteLines quote={quote} />
    {approve.isError && !priceChanged ? <p className="text-sm text-danger" role="alert">{jobErrorMessage(approve.error)}</p> : null}
    {decline.isError ? <p className="text-sm text-danger" role="alert">{jobErrorMessage(decline.error)}</p> : null}
    <div className="flex flex-wrap gap-3">
      <button type="button" className="desk-button-brand" disabled={approve.isPending || decline.isPending || expired} onClick={() => approve.mutate(quote.digest)}>
        {approve.isPending ? <><BoxArt size={16} mono />{t`Approving…`}</> : priceChanged ? t`Approve new price` : t`Approve quote`}</button>
      <button type="button" className="desk-button" disabled={approve.isPending || decline.isPending} onClick={() => setDeclining(true)}>{t`Decline`}</button>
    </div>
    {expired ? <p className="text-sm text-muted">{t`This quote has expired. Ask staff for a new one.`}</p> : null}
    <ConfirmDialog open={declining} title={t`Decline this quote?`} tone="danger" pending={decline.isPending}
      message={t`Declining cancels "${job.title}". Nothing is charged.`} confirmLabel={decline.isPending ? t`Declining…` : t`Decline and cancel`}
      cancelLabel={t`Keep the quote`} onConfirm={() => decline.mutate()} onCancel={() => setDeclining(false)} />
  </section>;
}
