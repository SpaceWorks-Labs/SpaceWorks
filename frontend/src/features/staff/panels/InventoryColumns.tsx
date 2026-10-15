import { ImageThumbnail } from "../../../components/ui/ImageThumbnail";
import { OverflowMenu, StatusBadge } from "../../../components/ui";
import type { DataTableColumn } from "../../../components/ui";
import { InventoryAvailability } from "./InventoryPanelParts";
import type { AdminProduct } from "./InventoryPanelShared";
export function inventoryColumns({ openEdit, openFix, openToBuy, archive, unarchive, canUseToBuy, pending }: {
 openEdit: (item: AdminProduct) => void; openFix: (item: AdminProduct) => void; openToBuy: (item: AdminProduct) => void;
 archive: (item: AdminProduct) => void; unarchive: (item: AdminProduct) => void; canUseToBuy: boolean; pending: boolean;
}): DataTableColumn<AdminProduct>[] {
 return [
 { key: "image", header: "", render: item => <ImageThumbnail src={item.image_url} alt={item.name} className="h-13 w-13" /> },
 { key: "name", header: "Item", sortable: true, render: item => <button className="desk-button-ghost text-left" onClick={() => openEdit(item)}>{item.name}</button> },
 { key: "tracking_mode", header: "Mode", sortable: true, render: item => <>{item.tracking_mode === "individual" ? "Individual" : "Count"}{item.is_archived ? <StatusBadge status="archived" /> : null}</> },
 { key: "total_quantity", header: "Total", sortable: true, className: "text-right tabular-nums" },
 { key: "available_quantity", header: "Available", sortable: true, className: "text-right tabular-nums", render: item => <InventoryAvailability product={item} /> },
 ...["issued_quantity", "damaged_quantity", "lost_quantity"].map(key => ({ key, header: key.replace("_quantity", "").replace(/^./, x => x.toUpperCase()), sortable: true, className: "text-right tabular-nums" })),
 { key: "actions", header: "", render: item => <OverflowMenu label={`Actions for ${item.name}`} actions={[
 { label: "Edit", onClick: () => openEdit(item) },
 ...(!item.is_archived ? [{ label: "Move to repair shelf", confirms: true, disabled: item.tracking_mode === "individual" ? item.available_quantity + item.damaged_quantity <= 0 : item.available_quantity <= 0, disabledReason: "No eligible units available.", onClick: () => openFix(item) }] : []),
 ...(canUseToBuy ? [{ label: "Add to To buy", confirms: true, onClick: () => openToBuy(item) }] : []),
 { label: item.is_archived ? "Back to inventory" : "Archive", disabled: pending, onClick: () => item.is_archived ? unarchive(item) : archive(item),
   ...(!item.is_archived ? { confirms: true, confirm: { title: `Archive ${item.name}?`, message: "It leaves the catalogue and can no longer be requested. You can bring it back from the Archived tab." } } : {}) },
 ]} /> },
 ];
}
