import { t } from "@lingui/core/macro";
import { toast } from "../../../components/ui/toastStore";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ListLayout } from "../../../components/layouts";
import { ConfirmDialog, ErrorText, ListRow, OverflowMenu, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { invalidateInventoryViews } from "../queryInvalidation";
import { inventoryQueryState } from "./inventoryPresentation";
import { QuantityStepper } from "../QuantityStepper";
import { type Makerspace, useStaffGet } from "./shared";
import type { ProblemReportsNav } from "./ProblemReportsQueue";

type ShelfItem = { id: number; name: string; needs_fix_quantity: number; available_quantity: number; total_quantity: number };
export function NeedsFixShelf({ makerspace, nav = {} }: { makerspace: Makerspace; nav?: ProblemReportsNav }) {
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
      toast(variables.action === "repair" ? (item?.name ? t`${variables.quantity} × ${item.name} back in stock.` : t`${variables.quantity} × Item back in stock.`) : t`Units scrapped.`);
      client.invalidateQueries({ queryKey: ["needs-fix-shelf", makerspace.id] });
      invalidateInventoryViews(client, makerspace.id);
    },
  });
  const rows = shelf.data?.results ?? [];
  const quantity = (item: ShelfItem) => Number(qty[item.id] ?? item.needs_fix_quantity);
  const valid = (item: ShelfItem) => Number.isInteger(quantity(item)) && quantity(item) >= 1 && quantity(item) <= item.needs_fix_quantity;
  const run = (item: ShelfItem, action: "repair" | "scrap") => { if (valid(item)) act.mutate({ id: item.id, action, quantity: quantity(item) }); };
  return <ListLayout header={{ title: t`Repair shelf`, subtitle: t`Units returned broken. Repair them back into stock, or scrap them.` }} {...nav}
    state={inventoryQueryState(shelf, "the repair shelf")} isEmpty={!rows.length}
    empty={{ message: t`Nothing on the shelf. Broken returns land here for repair.` }}
    stats={[{ label: t`Units to fix`, value: rows.reduce((sum, item) => sum + item.needs_fix_quantity, 0) }, { label: t`Products affected`, value: rows.length }]}
    body={{ kind: "rows", rows: rows.map(item => <ListRow key={item.id} title={item.name}
      identity={{ kind: "icon", icon: "Wrench", tone: "warn" }} meta={`${item.available_quantity} available · ${item.total_quantity} total`}
      right={<div className="flex flex-wrap items-end gap-3"><StatusPill tone="warn" label={t`${item.needs_fix_quantity} to fix`} />
        <label className="grid gap-1 text-sm">{t`Quantity`}<QuantityStepper label="quantity" min={1} max={item.needs_fix_quantity}
          value={qty[item.id] ?? String(item.needs_fix_quantity)} onValueChange={value => setQty(current => ({ ...current, [item.id]: value }))} /></label>
        <button className="desk-button self-end" disabled={act.isPending || !valid(item)} onClick={() => run(item, "repair")}>{act.isPending && act.variables?.id === item.id ? t`Repairing…` : t`Repaired`}</button>
        <OverflowMenu label={t`Actions for ${item.name}`} actions={[{ label: t`Scrap`, confirms: true, tone: "danger", onClick: () => setScrapTarget(item), disabled: act.isPending || !valid(item), disabledReason: act.isPending || !valid(item) ? t`Choose an eligible quantity.` : undefined }]} />
      </div>} />) }}
    detail={<><ErrorText message={act.error?.message} />
      <ConfirmDialog open={Boolean(scrapTarget)} title={scrapTarget ? t`Scrap ${quantity(scrapTarget)} × ${scrapTarget.name}?` : t`Scrap units?`}
        message={t`They're removed from inventory for good.`} confirmLabel={t`Scrap`} tone="danger" pending={act.isPending}
        onCancel={() => setScrapTarget(null)} onConfirm={() => { if (scrapTarget) run(scrapTarget, "scrap"); }} /></>} />;
}
