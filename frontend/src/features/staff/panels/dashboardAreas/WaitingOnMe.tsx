import { t } from "@lingui/core/macro";
import { RouteLink } from "../../../../components/ui/RouteLink";
import { areaLabel, attentionHref, isUrgent, itemLabel, type Attention, type AttentionItem, type AttentionRouting } from "./attention";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

/** One counter row: the number carries the emphasis pill, the area is named in words (never colour alone). */
export function AttentionRow({ item, area, routing }: { item: AttentionItem; area?: string; routing: AttentionRouting }) {
  const href = attentionHref(item.link, routing);
  const zero = item.count === 0;
  const pill = zero ? "text-muted" : isUrgent(item.key) ? "rounded-full bg-danger px-2.5 py-0.5 text-on-danger"
    : "rounded-full bg-emphasis px-2.5 py-0.5 text-on-emphasis";
  const body = <>
    <span className="min-w-0">
      <span className="block text-sm text-ink [overflow-wrap:anywhere]">{itemLabel(item.key)}</span>
      {area ? <span className="block text-xs text-muted">{areaLabel(area)}</span> : null}
    </span>
    <span className={`shrink-0 text-sm font-semibold tabular-nums ${pill}`}>{item.count}</span>
  </>;
  const classes = "flex min-h-12 items-center justify-between gap-3 rounded-xl border border-line bg-panel px-4 py-2";
  return href ? <RouteLink href={href} className={`${classes} hover:bg-hover ${FOCUS}`}>{body}</RouteLink> : <div className={classes}>{body}</div>;
}

export function AreaErrors({ errors, onRetry }: { errors: string[]; onRetry: () => void }) {
  if (!errors.length) return null;
  return <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-panel px-4 py-3 text-sm">
    <span className="min-w-0 flex-1">{t`Couldn't load: ${errors.map(areaLabel).join(", ")}. These numbers are missing, not zero.`}</span>
    <button type="button" className={`desk-button min-h-11 ${FOCUS}`} onClick={onRetry}>{t`Try again`}</button>
  </div>;
}

/** Decision 242(j): what needs this person now, across the areas they run, largest first. */
export function WaitingOnMe({ attention, routing, onRetry }: { attention: Attention; routing: AttentionRouting; onRetry: () => void }) {
  return <section aria-labelledby="waiting-on-me" className="grid gap-3">
    <h2 id="waiting-on-me" className="title-panel">{t`Waiting on me`}</h2>
    <AreaErrors errors={attention.errors} onRetry={onRetry} />
    {attention.waiting.length ? <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
      {attention.waiting.map(item => <li key={`${item.area}:${item.key}`}><AttentionRow item={item} area={item.area} routing={routing} /></li>)}
    </ul> : attention.errors.length ? null : <p className="rounded-xl border border-line bg-panel px-4 py-3 text-sm text-muted">
      {t`Nothing is waiting on you right now. New requests, approvals and overdue items will show up here.`}</p>}
  </section>;
}
