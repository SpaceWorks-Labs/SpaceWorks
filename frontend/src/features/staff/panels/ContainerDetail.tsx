import { EmptyState } from "../../../components/ui/EmptyState";
import { InventoryDetailNavigation } from "./InventoryDetailNavigation";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DetailLayout } from "../../../components/layouts";
import { OverflowMenu, RelativeTime, SettingsActions, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { WarrantySection } from "../WarrantySection";
import { invalidateContainerViews } from "../queryInvalidation";
import { useStaffGet } from "./shared";
import { QrImage } from "./QrImage";
import { KitDefinitionEditor } from "../../inventory/KitChecklist";
import { inventoryQueryState } from "./inventoryPresentation";
import type { Container } from "./ContainersPanel";
type Contents = {
  products: { id: number; name: string; available_quantity: number; tracking_mode: string }[];
  assets: { id: number; asset_tag: string; product: string; status: string }[];
  children: Container[];
};
type History = { scans: { id: string; source: string; context: string; actor: number | null; created_at: string }[] };

export function ContainerDetail({ container, makerspaceId, canEditInventory, kitEnabled, onClose }: { container: Container; makerspaceId: number; canEditInventory: boolean; kitEnabled: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const panel = params.get("containerTab") ?? "contents";
  const [label, setLabel] = useState(container.label);
  const [location, setLocation] = useState(container.location ?? "");
  const [isActive, setIsActive] = useState(container.is_active ?? true);
  const [components, setComponents] = useState(container.kit_components ?? []);

  const contents = useStaffGet<Contents>(["container-contents", container.id], `/admin/containers/${container.id}/contents`, panel === "contents");
  const history = useStaffGet<History>(["container-history", container.id], `/admin/containers/${container.id}/history`, panel === "history");

  const save = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/containers/${container.id}/move`, {
        method: "POST",
        body: JSON.stringify({ label: label.trim(), location: location.trim(), is_active: isActive,
          ...(kitEnabled ? { kit_components: components } : {}) }),
      }),
    onSuccess: () => {
      invalidateContainerViews(queryClient, makerspaceId, container.id);
    },
  });
  const saveError = save.error instanceof Error ? save.error.message : undefined;
  const href = (key: string) => { const next = new URLSearchParams(params); next.set("containerTab", key); return `?${next}`; };
  const query = panel === "contents" ? contents : panel === "history" ? history : null;
  return <InventoryDetailNavigation><DetailLayout presentation="drawer" open onClose={onClose} title={container.label} identity={{ kind: "code", code: container.code || String(container.id) }} meta={[container.code ?? "", container.location ?? ""]}
    status={<StatusPill label={container.is_active === false ? "Inactive" : "Active"} tone={container.is_active === false ? "neutral" : "success"} />}
    state={query ? inventoryQueryState(query, panel === "history" ? "scan history" : "container contents") : { status: "ready" }}
    tabs={["contents", "history", "details"].map(key => ({ key, label: key[0].toUpperCase() + key.slice(1), href: href(key) }))} activeTab={panel}
    main={<div className="grid gap-4">
      {panel === "details" ? (
        <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto] md:items-end">
          <label className="eyebrow grid min-w-0 gap-1"><span>Label</span><input className="desk-input min-w-0" value={label} onChange={(event) => setLabel(event.target.value)} /></label>
          <label className="eyebrow grid min-w-0 gap-1"><span>Location</span><input className="desk-input min-w-0" value={location} onChange={(event) => setLocation(event.target.value)} /></label>
          <label className="eyebrow flex items-center gap-2"><input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} /> Active</label>
          
        </div>
      ) : null}
      {saveError ? <p className="mt-2 text-danger">{saveError}</p> : null}
      {panel === "details" && kitEnabled ? <KitDefinitionEditor value={components} onChange={setComponents} /> : null}
      {panel === "details" && (label !== container.label || location !== (container.location ?? "") || isActive !== (container.is_active ?? true) || JSON.stringify(components) !== JSON.stringify(container.kit_components ?? [])) ? <SettingsActions pending={save.isPending} disabled={!label.trim()} onSave={() => save.mutate()} onDiscard={() => { setLabel(container.label); setLocation(container.location ?? ""); setIsActive(container.is_active ?? true); setComponents(container.kit_components ?? []); }} /> : null}
      {panel === "contents" ? (
        <div className="mt-3 grid gap-2 rounded-md border border-line bg-bg p-2">
          {contents.isLoading ? <p className="text-xs text-muted">Loading…</p> : null}
          <h4 className="title-section">Products</h4>
          {contents.error instanceof Error ? <p className="text-xs text-danger">{contents.error.message}</p> : null}
          {!contents.isLoading && !contents.error && contents.data?.products.length ? contents.data.products.map((product) => (
            <p key={product.id} className="text-xs text-muted">{product.name} - {product.available_quantity} available</p>
          )) : !contents.isLoading && !contents.error ? <p className="text-xs text-muted">This container is empty.</p> : null}
          <h4 className="title-section mt-1">Asset units</h4>
          {!contents.isLoading && !contents.error && contents.data?.assets.length ? contents.data.assets.map((asset) => (
            <AssetQrRow key={asset.id} asset={asset} canEditInventory={canEditInventory} />
          )) : !contents.isLoading && !contents.error ? <p className="text-xs text-muted">This container is empty.</p> : null}
          {contents.data?.children.length ? (
            <p className="mt-1 text-xs text-muted">Sub-containers: {contents.data.children.map((child) => child.label).join(", ")}</p>
          ) : null}
        </div>
      ) : null}

      {panel === "history" ? (
        <div className="mt-3 rounded-md border border-line bg-bg p-2">
          {history.isLoading ? <p className="text-xs text-muted">Loading…</p> : null}
          {history.error instanceof Error ? <p className="text-xs text-danger">{history.error.message}</p> : null}
          {!history.isLoading && !history.error && history.data?.scans.length ? history.data.scans.map((scan) => (
            <p key={scan.id} className="tabular-nums text-xs text-muted"><RelativeTime date={scan.created_at} /> · {scan.context || "Scan"} · {scan.source === "box_scan" ? "reviewed handover" : "QR scan"}</p>
          )) : !history.isLoading && !history.error ? <EmptyState message="No scans yet." /> : null}
        </div>
      ) : null}
    </div>} /></InventoryDetailNavigation>;
}

// Reprint a single unit's QR without rebuilding a whole batch: POST asset/<id>/qr is a
// get_or_create, so it returns the existing active QR (or makes one) and we render it.
function AssetQrRow({ asset, canEditInventory }: { asset: { id: number; asset_tag: string; product: string; status: string }; canEditInventory: boolean }) {
  const [qrId, setQrId] = useState<number | null>(null);
  const [showWarranty, setShowWarranty] = useState(false);
  const show = useMutation({
    mutationFn: () => staffRequest<{ id: number }>(`/admin/assets/${asset.id}/qr`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: (qr) => setQrId(qr.id),
  });
  return (
    <div className="min-w-0 rounded-md border border-line bg-surface p-2">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <span className="min-w-0 break-words">{asset.asset_tag}</span><StatusPill label={asset.status.replace(/_/g, " ")} />
        <button type="button" className="desk-button-ghost" disabled={show.isPending} onClick={() => show.mutate()}>{qrId ? "QR shown" : "Show QR"}</button>
        <OverflowMenu label={`Actions for ${asset.asset_tag}`} actions={[{ label: showWarranty ? "Hide warranty" : "Warranty", onClick: () => setShowWarranty(value => !value) }]} />
        {qrId ? <QrImage qrId={qrId} label={asset.asset_tag} /> : null}
        {show.error instanceof Error ? <span className="text-danger">{show.error.message}</span> : null}
      </div>
      {showWarranty ? <div className="mt-2"><WarrantySection hostKind="asset" hostId={asset.id} disabled={!canEditInventory} /></div> : null}
    </div>
  );
}
