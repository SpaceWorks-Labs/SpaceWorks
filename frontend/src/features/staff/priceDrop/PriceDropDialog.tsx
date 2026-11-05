import { Modal } from "../../../components/ui";
import { formatMoney } from "../paymentsApi";
import { AREA_LABELS, type PriceDropReport } from "./priceDropApi";

const when = (value: string | null) => value
  ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : null;

/**
 * Shown before a LOWER price is saved when people already paid for something not used yet.
 * Saving opens one refund case per item; the Space Manager or a finance admin approves each
 * one in the refund queue. Nothing is paid back automatically.
 */
export function PriceDropDialog({ report, onConfirm, onClose }: {
  report: PriceDropReport; onConfirm: () => void; onClose: () => void;
}) {
  const hidden = report.count - report.items.length;
  const totals = report.totals.map(row => formatMoney(row.difference, row.currency)).join(" + ");
  return <Modal open onClose={onClose} title="Lower this price?" footer={<div className="flex flex-wrap justify-end gap-3">
    <button type="button" className="desk-button" onClick={onClose}>Keep editing</button>
    <button type="button" className="desk-button-primary" onClick={onConfirm}>Save and open refunds</button>
  </div>}>
    <div className="grid gap-3 text-sm">
      <p className="text-ink">
        <span className="font-semibold">{report.count} paid {report.count === 1 ? "item" : "items"}</span> not used yet
        would cost less. Saving opens a refund case for each one, {totals} in all.
      </p>
      <p className="text-muted">The Space Manager or a finance admin approves every refund in the refund queue.
        Nothing is paid back until then, and people who paid the old price are never asked for more.</p>
      <ul tabIndex={0} aria-label="Paid items that would cost less"
        className="grid max-h-72 gap-1 overflow-y-auto rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
        {report.items.map(item => <li key={`${item.item_type}-${item.item_id}`}
          className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-line px-3 py-2">
          <span className="min-w-0 break-words">
            <span className="font-semibold text-ink">{AREA_LABELS[item.area] ?? "Item"} · {item.label}</span>
            {when(item.starts_at) ? <span className="text-muted"> · {when(item.starts_at)}</span> : null}
          </span>
          <span className="tabular-nums text-ink">
            {formatMoney(item.before, item.currency)} to {formatMoney(item.after, item.currency)}
            <span className="font-semibold"> · {formatMoney(item.difference, item.currency)} back</span>
          </span>
        </li>)}
      </ul>
      {hidden > 0 || report.truncated ? <p className="text-muted">And {Math.max(hidden, 0)} more not listed here.</p> : null}
    </div>
  </Modal>;
}
