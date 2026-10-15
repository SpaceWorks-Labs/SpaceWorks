import { ImageThumbnail } from "../../../components/ui/ImageThumbnail";
import { OverflowMenu, StatusBadge } from "../../../components/ui";
import type { DataTableColumn } from "../../../components/ui";
import { InventoryAvailability } from "./InventoryPanelParts";
import type { AdminProduct } from "./InventoryPanelShared";
export function inventoryColumns({ openEdit, openFix, openToBuy, archive, unarchive, canUseToBuy, pending, stockTab = false }: {
 openEdit: (item: AdminProduct) => void; openFix: (item: AdminProduct) => void; openToBuy: (item: AdminProduct) => void;
 archive: (item: AdminProduct) => void; unarchive: (item: AdminProduct) => void; canUseToBuy: boolean; pending: boolean;
 /** Low/out-of-stock tabs: "Add to To buy" is the frequent action, so it leaves the overflow. */
 stockTab?: boolean;
}): DataTableColumn<AdminProduct>[] {
 return [
 { key: "image", header: "", phone: "lead", render: item => <ImageThumbnail src={item.image_url} alt={item.name} className="h-13 w-13" /> },
 { key: "name", header: "Item", sortable: true, phone: "title", render: item => <button className="desk-button-ghost max-w-full justify-start text-left [overflow-wrap:anywhere]" onClick={() => openEdit(item)}>{item.name}</button> },
 { key: "tracking_mode", header: "Mode", sortable: true, render: item => <>{item.tracking_mode === "individual" ? "Individual" : "Count"}{item.is_archived ? <StatusBadge status="archived" /> : null}</> },
 { key: "total_quantity", header: "Total", sortable: true, className: "tabular-nums md:text-right" },
 { key: "available_quantity", header: "Available", sortable: true, phone: "status", className: "tabular-nums md:text-right", render: item => <InventoryAvailability product={item} /> },
 // On phones the table stacks into cards; the secondary counts drop out there (the item's Stock tab
 // still shows them) so each card stays short enough to scan with its action in view.
 ...["issued_quantity", "damaged_quantity", "lost_quantity"].map(key => ({ key, header: key.replace("_quantity", "").replace(/^./, x => x.toUpperCase()), sortable: true, className: "max-md:hidden tabular-nums md:text-right" })),
 { key: "actions", header: "", render: item => {
   // One context-aware frequent action stays visible; rare and destructive ones live in the overflow.
   const restoreVisible = item.is_archived;
   const toBuyVisible = !restoreVisible && stockTab && canUseToBuy;
   return <div className="flex flex-wrap items-center gap-2 md:justify-end">
     {restoreVisible ? <button type="button" className="desk-button-ghost" disabled={pending} onClick={() => unarchive(item)}>Restore</button> : null}
     {toBuyVisible ? <button type="button" className="desk-button-ghost" onClick={() => openToBuy(item)}>Add to To buy…</button> : null}
     <OverflowMenu label={`Actions for ${item.name}`} actions={[
       { label: "Edit", onClick: () => openEdit(item) },
       ...(!item.is_archived ? [{ label: "Move to repair shelf", confirms: true, disabled: item.tracking_mode === "individual" ? item.available_quantity + item.damaged_quantity <= 0 : item.available_quantity <= 0, disabledReason: "No eligible units available.", onClick: () => openFix(item) }] : []),
       ...(canUseToBuy && !toBuyVisible ? [{ label: "Add to To buy", confirms: true, onClick: () => openToBuy(item) }] : []),
       ...(!item.is_archived ? [{ label: "Archive", disabled: pending, onClick: () => archive(item), confirms: true,
         confirm: { title: `Archive ${item.name}?`, message: "It leaves the catalogue and can no longer be requested. You can bring it back from the Archived tab." } }] : []),
     ]} />
   </div>;
 } },
 ];
}
