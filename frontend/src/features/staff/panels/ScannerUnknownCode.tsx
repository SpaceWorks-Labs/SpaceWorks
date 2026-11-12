import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { StructuredApiError } from "../../../lib/api/errors";
import { useDebouncedValue } from "../../../lib/useDebouncedValue";
import { rows, type ListResponse, type Rebound, type ResolveTarget } from "./ScannerPanelTypes";
import { type Makerspace, type Product, useStaffGet } from "./shared";
import { BoxArt } from "../../../components/BoxSpinner";

type Unit = { id: number; asset_tag: string; qr_code_id: number | null };
type Conflict = { code?: string; detail?: string; target?: ResolveTarget };
type LinkBody = { product_id?: number; asset_id?: number; create_product?: Record<string, unknown>; create_asset?: { product_id: number; asset_tag: string } };
const NEW_UNIT = "new";

export function targetLabel(target: ResolveTarget) {
  return target.type === "box" ? t`Box: ${target.label}`
    : target.type === "product" ? t`Product: ${target.name}`
    : t`Asset: ${target.asset_tag} - ${target.product}`;
}

// A scanned code SpaceWorks does not know: staff with QR management can register a label
// printed elsewhere by creating an item for it or linking it to an existing item/unit.
// The server never reassigns a linked code; a 409 shows the item it already belongs to.
export function ScannerUnknownCode({ makerspace, value, canCreate, onLinked, onCancel }: {
  makerspace: Makerspace;
  value: string;
  canCreate: boolean;
  onLinked: (result: Rebound) => void;
  onCancel: () => void;
}) {
  const [mode, setMode] = useState<"choose" | "create" | "link">("choose");
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [search, setSearch] = useState("");
  const [productId, setProductId] = useState("");
  const [unitId, setUnitId] = useState("");
  const [newTag, setNewTag] = useState("");
  const [confirming, setConfirming] = useState(false);
  const query = useDebouncedValue(search.trim());
  const products = useStaffGet<ListResponse<Product>>(
    ["external-qr-products", makerspace.id, query],
    `/admin/makerspace/${makerspace.id}/inventory?page_size=20&archived=false${query ? `&q=${encodeURIComponent(query)}` : ""}`,
    mode === "link",
  );
  const product = rows(products.data).find((row) => String(row.id) === productId);
  const individual = product?.tracking_mode === "individual";
  const units = useStaffGet<ListResponse<Unit>>(["inventory-assets", Number(productId)], `/admin/inventory/${productId}/assets?page_size=1000`, mode === "link" && individual);
  const link = useMutation({
    mutationFn: (body: LinkBody) => staffRequest<Rebound>("/admin/qr/external", {
      method: "POST", body: JSON.stringify({ makerspace_id: makerspace.id, value, ...body }),
    }),
    onSuccess: onLinked,
  });
  const conflict = link.error instanceof StructuredApiError && link.error.status === 409 ? link.error.body as Conflict : null;
  const linkError = link.error && !conflict ? link.error.message : "";
  const unit = rows(units.data).find((row) => String(row.id) === unitId);
  const choice = !product ? "" : !individual ? product.name : unitId === NEW_UNIT ? (newTag.trim() ? t`${product.name} - new unit ${newTag.trim()}` : "") : unit ? `${product.name} - ${unit.asset_tag}` : "";
  const linkBody = (): LinkBody => !individual ? { product_id: Number(productId) }
    : unitId === NEW_UNIT ? { create_asset: { product_id: Number(productId), asset_tag: newTag.trim() } } : { asset_id: Number(unitId) };
  const total = Math.max(1, Number(quantity) || 1);

  return <section aria-label={t`Unrecognized QR code`} className="mt-4 grid gap-3 rounded-md border border-line bg-surface p-3 text-sm">
    <h3 className="title-section">{t`This QR code isn't linked to anything yet`}</h3>
    <label className="grid gap-1"><span className="eyebrow">{t`Scanned code`}</span>
      <input className="desk-input code-text" value={value} readOnly /></label>
    {conflict ? <div role="alert" className="rounded-md border border-line bg-bg p-2">
      <p>{conflict.detail}</p>
      {conflict.target ? <p className="font-medium">{t`Linked to ${targetLabel(conflict.target)}`}</p> : null}
    </div> : null}
    {linkError ? <p role="alert" className="text-danger">{linkError}</p> : null}
    {mode === "choose" ? <div className="desk-actions flex flex-wrap gap-2">
      {canCreate ? <button className="desk-button" type="button" onClick={() => setMode("create")}>{t`Create new item`}</button> : null}
      <button className="desk-button" type="button" onClick={() => setMode("link")}>{t`Link to existing item`}</button>
      <button className="desk-button-ghost" type="button" onClick={onCancel}>{t`Cancel`}</button>
    </div> : null}
    {mode === "create" ? <form className="grid gap-2" onSubmit={(event) => {
      event.preventDefault();
      if (name.trim()) link.mutate({ create_product: { name: name.trim(), total_quantity: total, available_quantity: total, tracking_mode: "quantity" } });
    }}>
      <label className="grid gap-1"><span className="eyebrow">{t`Item name`}</span>
        <input className="desk-input" value={name} required onChange={(event) => setName(event.target.value)} /></label>
      <label className="grid gap-1"><span className="eyebrow">{t`Quantity`}</span>
        <input className="desk-input" type="number" min={1} value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label>
      <p className="text-xs text-muted">{t`The scanned code is linked when the item is saved.`}</p>
      <div className="desk-actions flex flex-wrap gap-2">
        <button className="desk-button" type="submit" disabled={link.isPending || !name.trim()}>{link.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save item and link code`}</button>
        <button className="desk-button-ghost" type="button" onClick={() => setMode("choose")}>{t`Back`}</button>
      </div>
    </form> : null}
    {mode === "link" ? <div className="grid gap-2">
      <label className="grid gap-1"><span className="eyebrow">{t`Find item`}</span>
        <input className="desk-input" type="search" value={search} onChange={(event) => { setSearch(event.target.value); setConfirming(false); }} /></label>
      <label className="grid gap-1"><span className="eyebrow">{t`Item`}</span>
        <select className="desk-input" value={productId} disabled={products.isLoading} onChange={(event) => { setProductId(event.target.value); setUnitId(""); setConfirming(false); }}>
          <option value="">{products.isLoading ? t`Loading…` : t`Choose an item`}</option>
          {rows(products.data).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select></label>
      {individual ? <label className="grid gap-1"><span className="eyebrow">{t`Unit`}</span>
        <select className="desk-input" value={unitId} disabled={units.isLoading} onChange={(event) => { setUnitId(event.target.value); setConfirming(false); }}>
          <option value="">{t`Choose a unit`}</option>
          {rows(units.data).map((row) => <option key={row.id} value={row.id} disabled={row.qr_code_id !== null}>{row.qr_code_id !== null ? t`${row.asset_tag} (already has a QR code)` : row.asset_tag}</option>)}
          {canCreate ? <option value={NEW_UNIT}>{t`+ Add a new unit`}</option> : null}
        </select></label> : null}
      {individual && unitId === NEW_UNIT ? <label className="grid gap-1"><span className="eyebrow">{t`New unit tag`}</span>
        <input className="desk-input" value={newTag} onChange={(event) => { setNewTag(event.target.value); setConfirming(false); }} /></label> : null}
      {confirming && choice ? <p role="status">{t`Link this code to ${choice}? Existing links are never replaced.`}</p> : null}
      <div className="desk-actions flex flex-wrap gap-2">
        {confirming && choice
          ? <button className="desk-button" type="button" disabled={link.isPending} onClick={() => link.mutate(linkBody())}>{link.isPending ? <><BoxArt size={16} mono />{t`Linking…`}</> : t`Confirm link`}</button>
          : <button className="desk-button" type="button" disabled={!choice} onClick={() => setConfirming(true)}>{t`Link code`}</button>}
        <button className="desk-button-ghost" type="button" onClick={() => { setMode("choose"); setConfirming(false); }}>{t`Back`}</button>
      </div>
    </div> : null}
  </section>;
}
