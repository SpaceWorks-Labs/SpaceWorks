import { InventoryPublicPreview } from "./InventoryPublicPreview";
import type { ReactNode } from "react";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Field, StatusBadge, StatCard, DataTable, EmptyState, ErrorBlock, ListRow, Modal, OverflowMenu, RelativeTime, Skeleton } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { QrImage } from "./QrImage";
import { AssetEditForm } from "./AssetEditForm";
import { FormPageLayout } from "../../../components/layouts";
import { InventoryItemFields } from "./InventoryItemFields";
import { type Category, useStaffGet } from "./shared";
import {
  formatActor,
  humanize,
  type Actor,
  type AdjustmentForm,
  type AdminProduct,
  type InventoryAssetRow,
  type ItemForm,
  type LendingHistoryResponse,
  type QrHistoryResponse,
} from "./InventoryPanelShared";

export function ItemModal({ title, open, onClose, pending, onSubmit, ...fields }: {
  title: string; open: boolean; onClose: () => void; form: ItemForm; setForm: (updater: (current: ItemForm) => ItemForm) => void; categories: Category[];
  includeQuantities?: boolean; pending: boolean; error?: string; onSubmit: () => void; children?: ReactNode;
}) {
  if (!open) return null;
  return <FormPageLayout header={{ title, subtitle: "Add a part to your Space Works catalogue." }} state={{ status: "ready" }}
    form={<InventoryItemFields {...fields} />} submit={{ label: "Add item", pending, pendingLabel: "Adding…", disabled: !fields.form.name.trim(), disabledReason: "Enter an item name.", onClick: onSubmit }}
    cancel={{ label: "Cancel", onClick: onClose }} preview={{ label: "Public catalogue preview", content: <InventoryPublicPreview form={fields.form} category={fields.categories.find(category => String(category.id) === fields.form.category)?.name} /> }} />;
}

export function QuantityAdjust({ product, form, setForm, pending, error, onSubmit }: { product: AdminProduct; form: AdjustmentForm; setForm: (updater: (current: AdjustmentForm) => AdjustmentForm) => void; pending: boolean; error?: string; onSubmit: () => void }) {
  return (
    <div className="grid gap-3 border-t border-line pt-3">
      <h3 className="title-section">Adjust quantities</h3>
      <div className="grid gap-2 sm:grid-cols-3"><InventoryMetric label="Available" value={product.available_quantity} /><InventoryMetric label="Damaged" value={product.damaged_quantity} /><InventoryMetric label="Lost" value={product.lost_quantity} /></div>
      <div className="grid gap-2 sm:grid-cols-3"><Field label="± Available"><input className="desk-input" type="number" value={form.delta_available} onChange={(e) => setForm((c) => ({ ...c, delta_available: e.target.value }))} /></Field><Field label="± Damaged"><input className="desk-input" type="number" value={form.delta_damaged} onChange={(e) => setForm((c) => ({ ...c, delta_damaged: e.target.value }))} /></Field><Field label="± Lost"><input className="desk-input" type="number" value={form.delta_lost} onChange={(e) => setForm((c) => ({ ...c, delta_lost: e.target.value }))} /></Field></div>
      <Field label="Adjustment reason"><input className="desk-input" value={form.reason} onChange={(e) => setForm((c) => ({ ...c, reason: e.target.value }))} /></Field>
      {!form.reason.trim() ? <p className="text-sm text-muted">Add an adjustment reason to continue.</p> : null}
      <div className="desk-actions flex justify-end"><button className="desk-button-primary" type="button" disabled={pending || !form.reason.trim()} onClick={onSubmit}>{pending ? "Applying…" : "Apply adjustment"}</button></div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
    </div>
  );
}

export function QrHistory({ title, queryKey, path, defaultOpen = false }: { title: string; queryKey: unknown[]; path: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const history = useStaffGet<QrHistoryResponse>(queryKey, path, open);
  const rows = history.data?.scans ?? [];
  return (
    <div className="grid w-full gap-2 border-t border-line pt-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="title-section">{title}</h3>
        <button className="desk-button-ghost" type="button" onClick={() => setOpen((value) => !value)}>{open ? "Hide" : "History"}</button>
      </div>
      {open && history.isLoading ? <Skeleton className="h-32" /> : null}
      {open && history.error ? <ErrorBlock error={history.error} resource="history" onRetry={() => { void history.refetch(); }} /> : null}
      {open && !history.isLoading && !rows.length ? <EmptyState message="No QR scans recorded. Future scans will appear here." /> : null}
      {open && rows.length ? <div className="grid gap-3">{rows.map(scan => <ListRow key={scan.id} title={humanize(scan.context)} meta={<RelativeTime date={scan.created_at} />} right={scan.actor ? <span className="text-sm text-muted">User {scan.actor}</span> : null} />)}</div> : null}

    </div>
  );
}

export function IndividualAssets({ productId, makerspaceId, refreshInventory }: { productId: number; makerspaceId: number; refreshInventory: () => void }) {
  const queryClient = useQueryClient();
  const [editingAssetId, setEditingAssetId] = useState<number | null>(null);
  const [historyAssetId, setHistoryAssetId] = useState<number | null>(null);
  const assets = useStaffGet<{ results: InventoryAssetRow[] }>(["inventory-assets", productId], `/admin/inventory/${productId}/assets`);
  const containers = useStaffGet<{ results: { id: number; label: string }[] } | { id: number; label: string }[]>(
    ["containers-all", makerspaceId],
    `/admin/makerspace/${makerspaceId}/containers?page_size=1000`,
  );
  const containerOptions = Array.isArray(containers.data) ? containers.data : containers.data?.results ?? [];
  const saveAsset = () => {
    setEditingAssetId(null);
    queryClient.invalidateQueries({ queryKey: ["inventory-assets", productId] });
    refreshInventory();
  };
  const action = useMutation({
    mutationFn: ({ assetId, action }: { assetId: number; action: "shelve" | "repair" }) =>
      staffRequest(`/admin/assets/${assetId}/fix-status`, {
        method: "POST",
        body: JSON.stringify({ action }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inventory-assets", productId] });
      queryClient.invalidateQueries({ queryKey: ["needs-fix-shelf", makerspaceId] });
      refreshInventory();
    },
  });
  const rows = assets.data?.results ?? [];
  const selected = rows.find(asset => asset.id === editingAssetId);
  return <section className="mt-6 grid gap-4"><h3 className="title-section">Individual assets</h3>
    {assets.isLoading ? <Skeleton className="h-40" /> : assets.error ? <ErrorBlock error={assets.error} resource="assets" onRetry={() => { void assets.refetch(); }} /> : <DataTable data={rows} getRowId={asset => asset.id} emptyTitle="No asset records yet" columns={[
      { key: "asset_tag", header: "Asset", render: asset => <div><strong>{asset.asset_tag}</strong><p className="text-xs text-muted">{asset.serial_number}</p></div> },
      { key: "box_label", header: "Container" },
      { key: "status", header: "Status", render: asset => <StatusBadge status={asset.status} /> },
      { key: "qr", header: "QR", render: asset => asset.qr_code_id ? <details><summary className="desk-button-ghost">Show QR</summary><QrImage qrId={asset.qr_code_id} label={asset.asset_tag} /><p className="break-all text-xs">{asset.qr_payload}</p></details> : "No QR linked" },
      { key: "actions", header: "", render: asset => <div className="flex flex-wrap items-center gap-2">
        <button className="desk-button-ghost" disabled={action.isPending || (asset.status !== "maintenance" && !["available", "damaged"].includes(asset.status))}
          onClick={() => action.mutate({ assetId: asset.id, action: asset.status === "maintenance" ? "repair" : "shelve" })}>{action.isPending && action.variables?.assetId === asset.id ? "Updating…" : asset.status === "maintenance" ? "Move back to inventory" : "To fix"}</button>
        <OverflowMenu label={`Actions for ${asset.asset_tag}`} actions={[{ label: "Edit", onClick: () => setEditingAssetId(asset.id) }, { label: "QR history", onClick: () => setHistoryAssetId(asset.id) }]} />
      </div> },
    ]} />}
    {action.error ? <ErrorBlock error={action.error} /> : null}
    <Modal open={Boolean(selected)} onClose={() => setEditingAssetId(null)} title={selected ? `Edit ${selected.asset_tag}` : "Edit asset"}>
      {selected ? <AssetEditForm key={selected.id} asset={selected} containers={containerOptions} onSaved={saveAsset} onCancel={() => setEditingAssetId(null)} /> : null}
    </Modal>
    <Modal open={historyAssetId !== null} onClose={() => setHistoryAssetId(null)} title="Asset QR history">{historyAssetId ? <QrHistory key={historyAssetId} defaultOpen title="Asset QR history" queryKey={["asset-qr-history", historyAssetId]} path={`/admin/assets/${historyAssetId}/qr-history`} /> : null}</Modal>
  </section>;
}

export function LendingHistory({ productId }: { productId: number }) {
  const history = useStaffGet<LendingHistoryResponse>(["lending-history", productId], `/admin/inventory/${productId}/lending-history`);
  const last = history.data?.last_borrower;
  const recent = history.data?.recent ?? [];
  return <section className="grid gap-4"><h3 className="title-section">Lending history</h3>
    {history.isLoading ? <Skeleton className="h-40" /> : history.error ? <ErrorBlock error={history.error} resource="lending history" onRetry={() => { void history.refetch(); }} /> : !recent.length ? <EmptyState message="No lending history yet. Handovers will appear here." /> : null}
    {last ? <p className="text-sm">Last borrower: {last.username} · <RelativeTime date={last.issued_at} /><AttributionLine acceptedBy={last.accepted_by} issuedBy={last.issued_by} /></p> : null}
    {recent.map(entry => <ListRow key={entry.id} title={entry.username} identity={{ kind: "avatar", name: entry.username, seed: entry.username }} meta={<><RelativeTime date={entry.issued_at} /><AttributionLine acceptedBy={entry.accepted_by} issuedBy={entry.issued_by} /></>} right={<span className="tabular-nums">{entry.quantity} units</span>} />)}
  </section>;
}

export function InventoryAvailability({ product }: { product: AdminProduct }) {
  const isLowStock = product.available_quantity <= Math.ceil(product.total_quantity * 0.2);
  const badge = product.available_quantity <= 0 ? <StatusBadge status="unavailable" label="Unavailable" /> : isLowStock ? <StatusBadge status="limited" label="Limited" /> : <StatusBadge status="available" label="Available" />;
  return <span className="inline-flex items-center gap-2"><span className="inline-block w-8 font-medium tabular-nums text-ink">{product.available_quantity}</span>{badge}</span>;
}

export function InventoryMetric({ label, value }: { label: string; value: number }) {
  return <StatCard label={label} value={value} />;
}

export function AttributionLine({ acceptedBy, issuedBy }: { acceptedBy: Actor | null; issuedBy: Actor | null }) {
  const parts = [
    acceptedBy ? `Accepted by ${formatActor(acceptedBy)}` : "",
    issuedBy ? `Issued by ${formatActor(issuedBy)}` : "",
  ].filter(Boolean);
  return parts.length ? <p className="text-xs text-muted">{parts.join(" | ")}</p> : null;
}
