import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import type { Product } from "../../types/inventory";
import type { TenantBootstrap } from "../../lib/api";
import { PublicRequestPanel } from "./PublicRequestPanel";
import { clearStashedCart, readStashedCart } from "./publicInventory/cartHandoff";
import { useRequestDraft } from "./useRequestDraft";

export function useItemRequestDraft(id: string | null) {
  const [quantity, setQuantity] = useState(() => id ? readStashedCart()[Number(id)]?.quantity ?? 1 : 1);
  const [returning] = useState(() => Boolean(id && readStashedCart()[Number(id)]));
  const draft = useRequestDraft();
  useEffect(() => { clearStashedCart(); }, []);
  return { quantity, setQuantity, draft, returning };
}

export function ItemRequestForm({ product, bootstrap, state }: {
  product: Product; bootstrap: TenantBootstrap; state: ReturnType<typeof useItemRequestDraft>;
}) {
  const maximum = Math.min(99, product.availability?.mode === "exact_count" ? product.availability.count ?? 99 : 99);
  const quantity = Math.min(state.quantity, maximum);
  const unavailable = product.availability?.label === "Unavailable" || maximum < 1;
  if (unavailable) return <p role="status">{t`Not available to borrow right now`}</p>;
  return <div className="grid gap-4">
    <label className="grid gap-2 text-sm font-semibold">{t`Quantity`}
      <input className="desk-input w-full" type="number" min={1} max={maximum} value={quantity}
        onChange={event => { const value = Number(event.target.value); if (Number.isInteger(value) && value >= 1 && value <= maximum) state.setQuantity(value); }} />
    </label>
    <PublicRequestPanel items={quantity > 0 ? [{ productId: product.id, name: product.name, quantity }] : []}
      makerspaceSlug={bootstrap.makerspace.slug} makerspaceId={bootstrap.makerspace.id}
      modules={bootstrap.modules} features={bootstrap.features.filter(feature => feature !== "inventory.self_checkout")}
      contextual={false} requestAccess={bootstrap.makerspace.request_access} draft={state.draft} onClear={() => state.setQuantity(0)} />
  </div>;
}
