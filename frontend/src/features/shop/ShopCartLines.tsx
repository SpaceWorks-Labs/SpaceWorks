import { t } from "@lingui/core/macro";
import { Minus, Plus, Trash2 } from "lucide-react";

import { shopMoney } from "./shopApi";
import type { CartLine } from "./useShopCart";

/** Basket rows with quantity steppers. 44px targets; every control names the line it changes. */
export function ShopCartLines({ lines, currency, onQuantity, onRemove, disabled = false }: {
  lines: CartLine[]; currency: string; onQuantity: (variantId: number, quantity: number) => void;
  onRemove: (variantId: number) => void; disabled?: boolean;
}) {
  if (!lines.length) return <p className="text-sm text-muted">{t`Your basket is empty.`}</p>;
  return <ul className="grid gap-3" aria-label={t`Basket`}>
    {lines.map(line => <li key={line.variantId} className="flex min-w-0 flex-wrap items-center gap-3 rounded-xl border border-line p-3">
      <span className="grid min-w-0 flex-1 basis-40 gap-0.5">
        <span className="break-words font-semibold text-ink">{line.label}</span>
        <span className="text-sm tabular-nums text-muted">{shopMoney(line.price, currency)} each</span>
      </span>
      <span className="flex items-center gap-1">
        <button type="button" className="desk-button min-h-11 min-w-11 px-0" aria-label={t`One fewer ${line.label}`} disabled={disabled}
          onClick={() => onQuantity(line.variantId, line.quantity - 1)}><Minus aria-hidden="true" size={18} /></button>
        <output className="min-w-8 text-center font-semibold tabular-nums" aria-label={`${line.quantity} of ${line.label}`}>{line.quantity}</output>
        <button type="button" className="desk-button min-h-11 min-w-11 px-0" aria-label={t`One more ${line.label}`}
          disabled={disabled || Boolean(line.max && line.quantity >= line.max)} title={line.max && line.quantity >= line.max ? t`At most ${line.max} per order` : undefined}
          onClick={() => onQuantity(line.variantId, line.quantity + 1)}><Plus aria-hidden="true" size={18} /></button>
        <button type="button" className="desk-button-ghost min-h-11 min-w-11 px-0 text-danger" aria-label={t`Remove ${line.label}`} disabled={disabled}
          onClick={() => onRemove(line.variantId)}><Trash2 aria-hidden="true" size={18} /></button>
      </span>
    </li>)}
  </ul>;
}
