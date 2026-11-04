import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ListLayout } from "../../../components/layouts";
import { ListRow, OverflowMenu, StatusPill } from "../../../components/ui";
import { featureEnabled } from "../../../lib/features";
import type { KitComponent } from "../../inventory/KitChecklist";
import { ContainerCreateModal } from "./ContainerCreateModal";
import { ContainerDetail } from "./ContainerDetail";
import { inventoryQueryState } from "./inventoryPresentation";
import { type Makerspace, useStaffGet } from "./shared";
export type Container = { id: number; code?: string; label: string; location?: string; is_active?: boolean; kit_components?: KitComponent[] };
export function ContainersPanel({ makerspace, canEditInventory }: { makerspace: Makerspace; canEditInventory: boolean }) {
 const [params, setParams] = useSearchParams();
 const containers = useStaffGet<{ results: Container[] }>(["containers", makerspace.id], `/admin/makerspace/${makerspace.id}/containers?page_size=1000`);
 const search = params.get("q") ?? "";
 const status = params.get("view") ?? "all";
 const rows = (containers.data?.results ?? []).filter(row => row.label.toLowerCase().includes(search.toLowerCase()) && (status === "all" || (status === "active" ? row.is_active !== false : row.is_active === false)));
 const selected = containers.data?.results.find(row => String(row.id) === params.get("container"));
 const href = (view: string) => { const next = new URLSearchParams(params); next.set("view", view); return `?${next}`; };
 const [createOpen, setCreateOpen] = useState(false);
 const create = { label: "New container", icon: "Plus" as const, onClick: () => setCreateOpen(true) };
 const openContainer = (id: number, tab?: string) => setParams(current => { current.set("container", String(id)); if (tab) current.set("containerTab", tab); else current.delete("containerTab"); return current; });
 return <ListLayout header={{ title: "Containers", subtitle: "Boxes, bins and shelves with QR labels.", primary: create }}
   state={inventoryQueryState(containers, "containers")} isEmpty={!rows.length} filtered={Boolean(search || status !== "all")}
   empty={{ message: "No containers yet. Create a labelled box, bin or shelf.", action: create }}
   filteredEmpty={{ message: "Nothing matches these filters.", action: { label: "Clear filters", onClick: () => setParams(current => { current.delete("q"); current.delete("view"); return current; }) } }}
   tabs={["all", "active", "inactive"].map(key => ({ key, label: key[0].toUpperCase() + key.slice(1), href: href(key) }))} activeTab={status}
   filters={{ search: { label: "Search containers", value: search, onChange: value => setParams(current => { current.set("q", value); return current; }) } }}
   body={{ kind: "rows", rows: rows.map(container => <ListRow key={container.id} title={container.label} identity={{ kind: "code", code: container.code || String(container.id) }}
     meta={[container.code, container.location].filter(Boolean).join(" · ")} onClick={() => openContainer(container.id)}
     right={<div className="flex items-center gap-2"><StatusPill label={container.is_active === false ? "Inactive" : "Active"} tone={container.is_active === false ? "neutral" : "success"} />
       <OverflowMenu label={`Actions for ${container.label}`} actions={[{ label: "Edit", onClick: () => openContainer(container.id, "details") }, { label: "Scan history", onClick: () => openContainer(container.id, "history") }]} /></div>} />) }}
   detail={<><ContainerCreateModal makerspaceId={makerspace.id} open={createOpen} onClose={() => setCreateOpen(false)} onCreated={created => { setCreateOpen(false); openContainer(created.id, "details"); }} />
     {selected ? <ContainerDetail key={selected.id} container={selected} makerspaceId={makerspace.id} canEditInventory={canEditInventory} kitEnabled={featureEnabled(makerspace.enabled_features ?? [], "loans.kit_checklist")}
       warrantyEnabled={featureEnabled(makerspace.enabled_features ?? [], "inventory.warranty")}
     onClose={() => setParams(current => { current.delete("container"); current.delete("containerTab"); return current; })} /> : null}</>} />;
}
