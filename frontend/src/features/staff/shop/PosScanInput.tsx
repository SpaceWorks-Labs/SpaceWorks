import { ScanBarcode } from "lucide-react";
import { forwardRef, useState } from "react";

export type TillItem = { variantId: number; label: string; sku: string; price: string; available: number; max: number | null };

/** Exact SKU first (what a barcode scanner types), then a unique name match; several matches are offered as choices. */
export function matchTillItems(items: TillItem[], text: string) {
  const term = text.trim().toLowerCase();
  if (!term) return [];
  const exact = items.filter(item => item.sku && item.sku.toLowerCase() === term);
  if (exact.length) return exact;
  return items.filter(item => item.label.toLowerCase().includes(term) || item.sku.toLowerCase().includes(term));
}

/**
 * The till's one input. A USB/Bluetooth scanner is a keyboard that types the SKU and presses Enter,
 * so scanning and typing share one path: Enter adds the item when it is unambiguous.
 */
export const PosScanInput = forwardRef<HTMLInputElement, { items: TillItem[]; onAdd: (item: TillItem) => void; disabled?: boolean }>(
  function PosScanInput({ items, onAdd, disabled = false }, ref) {
    const [text, setText] = useState("");
    const [message, setMessage] = useState("");
    const matches = matchTillItems(items, text);
    const add = (item: TillItem) => { onAdd(item); setText(""); setMessage(`Added ${item.label}.`); };
    return <div className="grid gap-2">
      <label className="grid gap-1 text-sm font-semibold text-ink" htmlFor="till-scan">Scan or type an item</label>
      <div className="flex items-center gap-2">
        <ScanBarcode aria-hidden="true" size={28} className="shrink-0 text-muted" />
        <input ref={ref} id="till-scan" className="desk-input min-h-14 flex-1 text-lg" autoComplete="off" disabled={disabled}
          placeholder="SKU, barcode or name, then Enter" value={text} aria-describedby="till-scan-status"
          onChange={event => { setText(event.target.value); setMessage(""); }}
          onKeyDown={event => {
            if (event.key !== "Enter") return;
            event.preventDefault();
            if (matches.length === 1) add(matches[0]);
            else setMessage(matches.length ? `${matches.length} items match. Choose one below.` : `Nothing matches “${text.trim()}”.`);
          }} />
      </div>
      <p id="till-scan-status" role="status" className="min-h-5 text-sm text-muted">{message}</p>
      {text.trim() && matches.length > 1 ? <ul className="grid gap-2 sm:grid-cols-2" aria-label="Matching items">
        {matches.slice(0, 8).map(item => <li key={item.variantId}>
          <button type="button" className="desk-button min-h-14 w-full justify-between text-left" disabled={item.available <= 0}
            onClick={() => add(item)}>
            <span className="min-w-0 break-words">{item.label}{item.sku ? <span className="block text-xs text-muted">{item.sku}</span> : null}</span>
            <span className="tabular-nums">{item.available > 0 ? item.price : "Sold out"}</span></button>
        </li>)}
      </ul> : null}
    </div>;
  });
