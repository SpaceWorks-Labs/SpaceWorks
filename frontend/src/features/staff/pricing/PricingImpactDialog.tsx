import { Modal } from "../../../components/ui";
import { formatMoney } from "../paymentsApi";
import { componentLabel, type PricingImpact } from "./pricingApi";

/** What a rate-card change reprices, shown before anything is saved. Custom and free items never move. */
export function PricingImpactDialog({ impact, areaLabel, pending, error, onConfirm, onClose }: {
  impact: PricingImpact; areaLabel: string; pending: boolean; error?: string | null;
  onConfirm: () => void; onClose: () => void;
}) {
  const hidden = impact.changed - impact.changes.length;
  return <Modal open onClose={onClose} title={`Save ${areaLabel.toLowerCase()} prices?`} footer={<div className="flex flex-wrap justify-end gap-3">
    <button type="button" className="desk-button" onClick={onClose} disabled={pending}>Keep editing</button>
    <button type="button" className="desk-button-primary" onClick={onConfirm} disabled={pending}>
      {pending ? "Saving…" : "Save prices"}</button>
  </div>}>
    <div className="grid gap-3 text-sm">
      <p className="text-muted">We checked {impact.items_checked} {impact.items_checked === 1 ? "item" : "items"}. Items with their own
        price, or set to free, keep it.</p>
      {impact.changed === 0 ? <p className="font-semibold text-ink">No item changes price.</p> : <>
        <p className="font-semibold text-ink">{impact.changed} {impact.changed === 1 ? "price changes" : "prices change"}:</p>
        <ul tabIndex={0} className="grid max-h-72 gap-1 overflow-y-auto rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          aria-label="Price changes">
          {impact.changes.map(change => <li key={`${change.target_type}-${change.target_id}-${change.component}`}
            className="flex flex-wrap justify-between gap-2 rounded-lg border border-line px-3 py-2">
            <span className="min-w-0 break-words"><span className="font-semibold text-ink">{change.label}</span>
              <span className="text-muted"> · {componentLabel(change.component)}</span></span>
            <span className="tabular-nums">{formatMoney(change.before, impact.currency)} to {formatMoney(change.after, impact.currency)}</span>
          </li>)}
        </ul>
        {hidden > 0 || impact.truncated ? <p className="text-muted">And {Math.max(hidden, 0)} more not listed here.</p> : null}
      </>}
      {error ? <p role="alert" className="text-danger">{error}</p> : null}
    </div>
  </Modal>;
}
