import { t } from "@lingui/core/macro";
import { useState } from "react";

import { useConsumableStock } from "./consumablesApi";
import type { ProfileDraft } from "./profileDraft";
import { poolUnitFor, productUnit } from "./profileUnits";
import { SearchField } from "../../../../../components/ui/SearchField";

/** Links a profile row to a stock pool (same unit family only) or a counted product (sheet, piece, use only). Never both. */
export function StockLinkPicker({ makerspaceId, typeId, draft, onChange }: {
  makerspaceId: number; typeId: number; draft: ProfileDraft; onChange: (patch: Partial<ProfileDraft>) => void;
}) {
  const [search, setSearch] = useState("");
  const stock = useConsumableStock(makerspaceId, typeId, productUnit(draft.unit) ? search.trim() : "");
  const wanted = poolUnitFor(draft.unit);
  const pools = (stock.data?.pools ?? []).filter(pool => pool.unit === wanted || pool.id === draft.consumable_pool);
  const products = stock.data?.products ?? [];
  if (!wanted && !productUnit(draft.unit)) return <p className="text-xs text-muted">{t`This unit is not tied to stock, so it can only be charged by price.`}</p>;
  return <div className="grid gap-2 sm:grid-cols-2">
    {wanted ? <label className="grid gap-1 text-sm">{t`Stock pool`}
      <select className="desk-input" value={draft.consumable_pool ?? ""} onChange={event => onChange({ consumable_pool: event.target.value ? Number(event.target.value) : null, product: null })}>
        <option value="">{t`Not linked`}</option>
        {pools.map(pool => <option key={pool.id} value={pool.id}>{`${pool.label} (${String(pool.remaining)} ${pool.unit})`}</option>)}
      </select></label> : null}
    {productUnit(draft.unit) ? <div className="grid gap-1 text-sm">
      <label className="grid gap-1">{t`Find a product`}<SearchField className="desk-input" value={search} placeholder={t`Type to search`} onChange={event => setSearch(event.target.value)} /></label>
      <label className="grid gap-1">{t`Linked product`}
        <select className="desk-input" value={draft.product ?? ""} onChange={event => onChange({ product: event.target.value ? Number(event.target.value) : null, consumable_pool: null })}>
          <option value="">{t`Not linked`}</option>
          {draft.product !== null && !products.some(product => product.id === draft.product) ? <option value={draft.product}>{t`Current product`}</option> : null}
          {products.map(product => <option key={product.id} value={product.id}>{product.name}</option>)}
        </select></label></div> : null}
    {stock.isError ? <p role="alert" className="text-xs text-danger sm:col-span-2">{t`Couldn't load stock. You can still save without a link.`}</p> : null}
  </div>;
}
