import { useId } from "react";
import { Tag } from "lucide-react";

import {
  isPriceOverrideCard, useStaffPricingOn, usePriceOverride, useSavePriceOverride, type PriceTargetType,
} from "./priceOverrideApi";
import { PriceOverrideRow } from "./PriceOverrideRow";

const statusOf = (error: unknown) => (error && typeof error === "object" ? (error as { status?: number }).status : undefined);

/**
 * An existing item's prices (lane L15): per component Inherit / Free / Custom and the price that
 * actually applies. Renders nothing while price lists are off (`charges.pricing`), when the server
 * answers 404, or when this account may not read prices (403). Read-only when `editable` is false.
 * `compact` folds it into a disclosure, for items listed several to a screen.
 */
export function PriceOverrideCard({ makerspaceId, targetType, targetId, compact = false }: {
  makerspaceId: number; targetType: PriceTargetType; targetId: number; compact?: boolean;
}) {
  const id = useId();
  const pricingOn = useStaffPricingOn(makerspaceId);
  const card = usePriceOverride(makerspaceId, targetType, targetId, pricingOn !== false);
  const save = useSavePriceOverride(makerspaceId, targetType, targetId);
  if (pricingOn === false || !isPriceOverrideCard(card.data)) {
    const status = statusOf(card.error);
    return card.error && status !== 404 && status !== 403
      ? <p role="alert" className="text-sm text-danger">Couldn't load this item's price.</p> : null;
  }
  const data = card.data;
  if (!data.components.length) return null;
  const body = <>
    <p className="text-sm text-muted">
      {data.editable ? "Inherit follows the space default in Settings > Pricing. Free makes this item free. Custom gives it its own price."
        : "Prices are set by staff who edit this item."}
    </p>
    <div className="divide-y divide-line">
      {data.components.map(row => <PriceOverrideRow key={`${row.component}:${row.mode}:${row.amount}:${row.cap}:${row.effective_amount}`}
        row={row} currency={data.currency} editable={data.editable} pending={save.isPending && save.variables?.component === row.component}
        onSave={body => save.mutate(body)} />)}
    </div>
    <p aria-live="polite" className="text-sm text-muted">{save.isSuccess && !save.isPending ? "Price saved." : ""}</p>
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error instanceof Error ? save.error.message : "Couldn't save the price."}</p> : null}
  </>;
  if (compact) return <details className="rounded-lg border border-line bg-panel">
    <summary className="flex min-h-11 cursor-pointer items-center gap-2 px-3 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
      <Tag aria-hidden="true" className="h-4 w-4 text-muted" />Price
    </summary>
    <div className="grid gap-3 border-t border-line p-3">{body}</div>
  </details>;
  return <section aria-labelledby={id} className="grid min-w-0 gap-3 rounded-xl border border-line bg-panel p-5">
    <h3 id={id} className="title-section flex items-center gap-2"><Tag aria-hidden="true" className="h-4 w-4 text-muted" />Price</h3>
    {body}
  </section>;
}
