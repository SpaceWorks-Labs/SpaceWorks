import { toast } from "../../../components/ui/toastStore";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ListLayout } from "../../../components/layouts";
import { ConfirmDialog, ErrorText, ListRow, OverflowMenu, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { invalidateInventoryViews } from "../queryInvalidation";
import { inventoryQueryState } from "./inventoryPresentation";
import { type Makerspace, useStaffGet } from "./shared";

type ShelfItem = { id: number; name: string; needs_fix_quantity: number; available_quantity: number; total_quantity: number };
export function NeedsFixShelf({ makerspace }: { makerspace: Makerspace }) {
  const client = useQueryClient();
  const shelf = useStaffGet<{ results: ShelfItem[] }>(["needs-fix-shelf", makerspace.id], `/admin/inventory/needs-fix?makerspace=${makerspace.id}`);
  const [qty, setQty] = useState<Record<number, string>>({});
  const [scrapTarget, setScrapTarget] = useState<ShelfItem | null>(null);
  const act = useMutation({
    mutationFn: ({ id, action, quantity }: { id: number; action: "repair" | "scrap"; quantity: number }) =>
      staffRequest(`/admin/inventory/${id}/needs-fix`, { method: "POST", body: JSON.stringify({ action, quantity }) }),
    onSuccess: (_data, variables) => {
      setScrapTarget(null);
      const item = shelf.data?.results.find(row => row.id === variables.id);
      toast(variables.action === "repair" ? `${variables.quantity} × ${item?.name ?? "Item"} back in stock.` : "Units scrapped.");
      client.invalidateQueries({ queryKey: ["needs-fix-shelf", makerspace.id] });
      invalidateInventoryViews(client, makerspace.id);
    },
  });
  const rows = shelf.data?.results ?? [];
  const quantity = (item: ShelfItem) => Number(qty[item.id] ?? item.needs_fix_quantity);
  const valid = (item: ShelfItem) => Number.isInteger(quantity(item)) && quantity(item) >= 1 && quantity(item) <= item.needs_fix_quantity;
  const run = (item: ShelfItem, action: "repair" | "scrap") => { if (valid(item)) act.mutate({ id: item.id, action, quantity: quantity(item) }); };
  return <ListLayout header={{ title: "To be fixed", subtitle: "Units returned broken. Repair them back into stock, or scrap them." }}
    state={inventoryQueryState(shelf, "the repair shelf")} isEmpty={!rows.length}
    empty={{ message: "Nothing on the shelf. Broken returns land here for repair." }}
    stats={[{ label: "Units to fix", value: rows.reduce((sum, item) => sum + item.needs_fix_quantity, 0) }, { label: "Products affected", value: rows.length }]}
    body={{ kind: "rows", rows: rows.map(item => <ListRow key={item.id} title={item.name}
      identity={{ kind: "icon", icon: "Wrench", tone: "warn" }} meta={`${item.available_quantity} available · ${item.total_quantity} total`}
      right={<div className="flex flex-wrap items-center gap-3"><StatusPill tone="warn" label={`${item.needs_fix_quantity} to fix`} />
        <label className="grid gap-1 text-sm">Quantity<input className="desk-input w-24" type="number" min="1" max={item.needs_fix_quantity}
          value={qty[item.id] ?? String(item.needs_fix_quantity)} onChange={event => setQty(current => ({ ...current, [item.id]: event.target.value }))} /></label>
        <button className="desk-button-ghost" disabled={act.isPending || !valid(item)} onClick={() => run(item, "repair")}>{act.isPending && act.variables?.id === item.id ? "Repairing…" : "Repaired"}</button>
        <OverflowMenu label={`Actions for ${item.name}`} actions={[{ label: "Scrap", confirms: true, tone: "danger", onClick: () => setScrapTarget(item), disabled: act.isPending || !valid(item), disabledReason: act.isPending || !valid(item) ? "Choose an eligible quantity." : undefined }]} />
      </div>} />) }}
    detail={<><ErrorText message={act.error?.message} />
      <ConfirmDialog open={Boolean(scrapTarget)} title={scrapTarget ? `Scrap ${quantity(scrapTarget)} × ${scrapTarget.name}?` : "Scrap units?"}
        message="They're removed from inventory for good." confirmLabel="Scrap" tone="danger" pending={act.isPending}
        onCancel={() => setScrapTarget(null)} onConfirm={() => { if (scrapTarget) run(scrapTarget, "scrap"); }} /></>} />;
}
