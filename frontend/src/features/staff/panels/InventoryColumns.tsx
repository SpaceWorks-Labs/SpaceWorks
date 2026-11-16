import { t } from "@lingui/core/macro";
import { ImageThumbnail } from "../../../components/ui/ImageThumbnail";
import { OverflowMenu, StatusBadge } from "../../../components/ui";
import type { DataTableColumn } from "../../../components/ui";
import { InventoryAvailability } from "./InventoryPanelParts";
import { assetStatusLabel, type AdminProduct } from "./InventoryPanelShared";
export function inventoryColumns({ openEdit, openFix, openToBuy, archive, unarchive, canUseToBuy, pending, stockTab = false }: {
 openEdit: (item: AdminProduct) => void; openFix: (item: AdminProduct) => void; openToBuy: (item: AdminProduct) => void;
 archive: (item: AdminProduct) => void; unarchive: (item: AdminProduct) => void; canUseToBuy: boolean; pending: boolean;
 /** Low/out-of-stock tabs: "Add to To buy" is the frequent action, so it leaves the overflow. */
 stockTab?: boolean;
}): DataTableColumn<AdminProduct>[] {
 return [
 { key: "image", header: "", phone: "lead", render: item => <ImageThumbnail src={item.image_url} alt={item.name} className="h-13 w-13" /> },
 { key: "name", header: t`Item`, sortable: true, phone: "title", render: item => <button className="desk-button-ghost max-w-full justify-start text-left [overflow-wrap:anywhere]" onClick={() => openEdit(item)}>{item.name}</button> },
 { key: "tracking_mode", header: t`Mode`, sortable: true, render: item => <>{item.tracking_mode === "individual" ? t`Individual` : t`Count`}{item.is_archived ? <StatusBadge status="archived" label={assetStatusLabel("archived")} /> : null}</> },
 { key: "total_quantity", header: t`Total`, sortable: true, className: "tabular-nums md:text-right" },
 { key: "available_quantity", header: t`Available`, sortable: true, phone: "status", className: "tabular-nums md:text-right", render: item => <InventoryAvailability product={item} /> },
 // On phones the table stacks into cards; the secondary counts drop out there (the item's Stock tab
 // still shows them) so each card stays short enough to scan with its action in view.
 ...([["issued_quantity", t`Issued`], ["damaged_quantity", t`Damaged`], ["lost_quantity", t`Lost`]] as const).map(([key, header]) => ({ key, header, sortable: true, className: "max-md:hidden tabular-nums md:text-right" })),
 { key: "actions", header: "", render: item => {
   // One context-aware frequent action stays visible; rare and destructive ones live in the overflow.
   const restoreVisible = item.is_archived;
   const toBuyVisible = !restoreVisible && stockTab && canUseToBuy;
   return <div className="flex flex-wrap items-center gap-2 md:justify-end">
     {restoreVisible ? <button type="button" className="desk-button-ghost" disabled={pending} onClick={() => unarchive(item)}>{t`Restore`}</button> : null}
     {toBuyVisible ? <button type="button" className="desk-button-ghost" onClick={() => openToBuy(item)}>{t`Add to To buy…`}</button> : null}
     <OverflowMenu label={t`Actions for ${item.name}`} actions={[
       { label: t`Edit`, onClick: () => openEdit(item) },
       ...(!item.is_archived ? [{ label: t`Move to repair shelf`, confirms: true, disabled: item.tracking_mode === "individual" ? item.available_quantity + item.damaged_quantity <= 0 : item.available_quantity <= 0, disabledReason: t`No eligible units available.`, onClick: () => openFix(item) }] : []),
       ...(canUseToBuy && !toBuyVisible ? [{ label: t`Add to To buy`, confirms: true, onClick: () => openToBuy(item) }] : []),
       ...(!item.is_archived ? [{ label: t`Archive`, disabled: pending, onClick: () => archive(item), confirms: true,
         confirm: { title: t`Archive ${item.name}?`, message: t`It leaves the catalogue and can no longer be requested. You can bring it back from the Archived tab.` } }] : []),
     ]} />
   </div>;
 } },
 ];
}
