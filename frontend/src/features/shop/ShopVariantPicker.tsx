import { t } from "@lingui/core/macro";
import { StatusPill } from "../../components/ui";
import { shopMoney, stockLabel, type ShopPublicProduct } from "./shopApi";

const optionText = (options: Record<string, string>) => Object.entries(options).map(([key, value]) => `${key}: ${value}`).join(", ");

/** One radio per variant, sold-out ones disabled; quantity is capped by the per-order limit when there is one. */
export function ShopVariantPicker({ product, currency, variantId, quantity, onVariant, onQuantity }: {
  product: ShopPublicProduct; currency: string; variantId: number | null; quantity: number;
  onVariant: (id: number) => void; onQuantity: (quantity: number) => void;
}) {
  const many = product.variants.length > 1;
  return <div className="grid gap-4">
    {many ? <fieldset className="grid gap-2">
      <legend className="mb-1 text-sm font-semibold text-ink">{t`Choose an option`}</legend>
      {product.variants.map(variant => {
        const stock = stockLabel(variant);
        const detail = optionText(variant.options ?? {});
        return <label key={variant.id} className={`flex min-h-11 flex-wrap items-center gap-3 rounded-xl border p-3 ${variantId === variant.id ? "border-ink" : "border-line"} ${variant.sold_out ? "opacity-70" : "cursor-pointer"}`}>
          <input type="radio" name={`variant-${product.id}`} value={variant.id} checked={variantId === variant.id} disabled={variant.sold_out}
            onChange={() => onVariant(variant.id)} />
          <span className="grid min-w-0 flex-1 gap-0.5">
            <span className="font-semibold text-ink">{variant.name || product.name}</span>
            {detail && detail !== variant.name ? <span className="text-sm text-muted">{detail}</span> : null}
          </span>
          <span className="tabular-nums">{shopMoney(variant.price, currency)}</span>
          {stock ? <StatusPill label={stock.label} tone={stock.tone} /> : null}
        </label>;
      })}
    </fieldset> : null}
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Quantity`}<input className="desk-input min-h-11 w-28 font-normal tabular-nums" type="number" min={1} max={product.max_per_order ?? undefined}
        value={quantity} onChange={event => onQuantity(Math.max(1, Math.min(Number(event.target.value) || 1, product.max_per_order ?? Infinity)))} />
    </label>
    {product.max_per_order ? <p className="text-sm text-muted">{t`At most ${product.max_per_order} per order.`}</p> : null}
  </div>;
}
