import { t } from "@lingui/core/macro";
import { Plus } from "lucide-react";

import { ShopOptionsEditor } from "./ShopOptionsEditor";

export type VariantRow = { key: string; id?: number; name: string; sku: string; price: string; reorder_point: number;
  sort_order?: number; linked_product_id: string; is_active: boolean; options: [string, string][]; on_hand?: number; available?: number };

export const blankVariant = (): VariantRow => ({ key: crypto.randomUUID(), name: "", sku: "", price: "", reorder_point: 0,
  linked_product_id: "", is_active: true, sort_order: 0, options: [] });

/** The product's sellable variants. Stock is changed in the Stock view, never here, so every move is recorded. */
export function ShopVariantsEditor({ rows, onChange, onArchive, linkConsumables, showReorder }: {
  rows: VariantRow[]; onChange: (rows: VariantRow[]) => void; onArchive: (row: VariantRow) => void;
  linkConsumables: boolean; showReorder: boolean;
}) {
  const set = (key: string, patch: Partial<VariantRow>) => onChange(rows.map(row => row.key === key ? { ...row, ...patch } : row));
  return <fieldset className="grid gap-3">
    <legend className="title-section mb-2">{t`Variants`}</legend>
    {rows.map((row, index) => {
      const name = row.name || `Variant ${index + 1}`;
      return <div key={row.key} className="grid gap-3 rounded-xl border border-line p-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="grid gap-1 text-sm font-semibold">{t`Name`}<input className="desk-input min-h-11 font-normal" value={row.name}
            placeholder={t`Standard`} onChange={event => set(row.key, { name: event.target.value })} /></label>
          <label className="grid gap-1 text-sm font-semibold">{t`SKU or barcode`}<input className="desk-input min-h-11 font-normal" value={row.sku}
            onChange={event => set(row.key, { sku: event.target.value })} /></label>
          <label className="grid gap-1 text-sm font-semibold">{t`Price`}<input className="desk-input min-h-11 font-normal tabular-nums" inputMode="decimal"
            required value={row.price} onChange={event => set(row.key, { price: event.target.value })} /></label>
          <label className="grid gap-1 text-sm font-semibold">{t`Display order for ${name}`}<input className="desk-input min-h-11 font-normal" type="number" step={1}
            value={row.sort_order ?? 0} onChange={event => set(row.key, { sort_order: Number(event.target.value) })} /></label>
          {showReorder ? <label className="grid gap-1 text-sm font-semibold">{t`Reorder at`}<input className="desk-input min-h-11 font-normal" type="number" min={0}
            value={row.reorder_point} onChange={event => set(row.key, { reorder_point: Math.max(0, Number(event.target.value) || 0) })} /></label> : null}
          {linkConsumables ? <label className="grid gap-1 text-sm font-semibold">{t`Inventory consumable ID`}<input className="desk-input min-h-11 font-normal" inputMode="numeric" value={row.linked_product_id}
              onChange={event => set(row.key, { linked_product_id: event.target.value.replace(/\D/g, "") })} />
            <span className="text-xs font-normal text-muted">{t`Sales then draw on that consumable's count.`}</span></label> : null}
        </div>
        <ShopOptionsEditor label={name} value={row.options} onChange={options => set(row.key, { options })} />
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={row.is_active}
            onChange={event => set(row.key, { is_active: event.target.checked })} />{t`On sale`}</label>
          {row.id !== undefined ? <span className="text-sm text-muted tabular-nums">{t`${row.on_hand ?? 0} on hand · ${row.available ?? 0} available`}</span> : null}
          {rows.length > 1 ? <button type="button" className="desk-button-danger-outline min-h-11 ml-auto" onClick={() => onArchive(row)}>
            {row.id !== undefined ? t`Archive ${name}` : t`Remove ${name}`}</button> : null}
        </div>
      </div>;
    })}
    <button type="button" className="desk-button min-h-11 justify-self-start" onClick={() => onChange([...rows, blankVariant()])}>
      <Plus aria-hidden="true" size={18} />{t`Add a variant`}</button>
  </fieldset>;
}
