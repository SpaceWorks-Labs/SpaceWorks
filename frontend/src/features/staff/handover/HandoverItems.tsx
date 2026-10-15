import type { HardwareRequest } from "../panels/Queues";
import type { ReturnRequestValues, AssetReturnOutcome } from "../panels/QueuesModalTypes";
import { QuantityStepper } from "../QuantityStepper";

export type Resolutions = ReturnRequestValues["resolutions"];
export const remaining = (item: HardwareRequest["items"][number]) => item.issued_quantity - item.returned_quantity - item.damaged_quantity - item.missing_quantity;
export function initialResolutions(row: HardwareRequest): Resolutions {
  return row.items.map(item => ({ item_id: item.id, returned: remaining(item), damaged: 0, missing: 0,
    ...(item.requires_asset_qr ? { assets: (item.issued_assets ?? []).map(asset => ({ asset_id: asset.asset_id, outcome: "returned" as const })) } : {}) }));
}
export function validResolutions(row: HardwareRequest, resolutions: Resolutions) {
  return resolutions.some(value => value.returned + value.damaged + value.missing > 0) && resolutions.every(value => {
    const item = row.items.find(item => item.id === value.item_id);
    return item && [value.returned, value.damaged, value.missing].every(value => Number.isInteger(value) && value >= 0) && value.returned + value.damaged + value.missing <= remaining(item);
  });
}
export function HandoverItems({ row, mode, resolutions, onChange }: { row: HardwareRequest; mode: "issue" | "return"; resolutions: Resolutions; onChange: (rows: Resolutions) => void }) {
  function quantity(id: number, key: "returned" | "damaged" | "missing", value: string) {
    onChange(resolutions.map(row => row.item_id === id ? { ...row, [key]: value === "" ? NaN : Number(value) } : row));
  }
  function assetOutcome(id: number, assetId: number, outcome: AssetReturnOutcome | "pending") {
    onChange(resolutions.map(value => {
      if (value.item_id !== id) return value;
      const item = row.items.find(item => item.id === id)!;
      const previous = new Map(value.assets?.map(asset => [asset.asset_id, asset.outcome]));
      previous.delete(assetId); if (outcome !== "pending") previous.set(assetId, outcome);
      const assets = (item.issued_assets ?? []).flatMap(asset => previous.has(asset.asset_id) ? [{ asset_id: asset.asset_id, outcome: previous.get(asset.asset_id)! }] : []);
      return { ...value, assets, returned: assets.filter(asset => asset.outcome === "returned").length, damaged: assets.filter(asset => asset.outcome === "damaged").length, missing: assets.filter(asset => asset.outcome === "missing").length };
    }));
  }
  // The list is a size container so the three counts sit side by side only when the work
  // column (not the viewport) has room for three thumb-sized steppers.
  return <div className="@container grid gap-3">{row.items.map(item => <fieldset key={item.id} className="grid min-w-0 gap-2 rounded border border-line p-3">
    <legend className="break-words px-1 font-semibold">{item.product_name}</legend>
    {mode === "issue" ? <p>Accepted quantity: {item.accepted_quantity}</p> : item.requires_asset_qr ? (item.issued_assets ?? []).map(asset => <label key={asset.asset_id} className="grid min-w-0 gap-1 break-words">{asset.asset_tag}
      <select className="desk-input" value={resolutions.find(value => value.item_id === item.id)?.assets?.find(value => value.asset_id === asset.asset_id)?.outcome ?? "pending"} onChange={event => assetOutcome(item.id, asset.asset_id, event.target.value as AssetReturnOutcome | "pending")}>
        <option value="returned">Returned</option><option value="damaged">Damaged</option><option value="missing">Missing</option><option value="pending">Not returned now</option>
      </select></label>) : <><p className="text-sm text-muted">Remaining: {remaining(item)}</p><div className="grid gap-3 @lg:grid-cols-3">{(["returned", "damaged", "missing"] as const).map(key => {
        const current = resolutions.find(value => value.item_id === item.id)?.[key];
        return <label key={key} className="grid min-w-0 gap-1 capitalize">{key}<QuantityStepper label={key} max={remaining(item)} value={Number.isNaN(current) ? "" : current ?? 0} onValueChange={value => quantity(item.id, key, value)} /></label>;
      })}</div></>}
  </fieldset>)}</div>;
}
