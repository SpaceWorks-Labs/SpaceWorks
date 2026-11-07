import { t } from "@lingui/core/macro";
import { toast } from "../../../components/ui/toastStore";
import type { Key } from "react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog, DataTable, Field, Modal, ErrorText } from "../../../components/ui";
import { useInventoryArchive } from "./useInventoryArchive";
import { useQuickCreate } from "../quickCreate";
import { inventoryColumns } from "./InventoryColumns";
import { QuantityStepper } from "../QuantityStepper";
import { downloadStaffFile, staffRequest } from "../../../lib/api";
import { useDebouncedValue } from "../../../lib/useDebouncedValue";
import { useUrlListState } from "../../../lib/useUrlListState";
import { ListLayout, DetailLayout } from "../../../components/layouts";
import { useSearchParams } from "react-router-dom";
import { inventoryQueryState } from "./inventoryPresentation";
import { InventoryItemDetail } from "./InventoryItemDetail";
import { ListViewControls } from "../ListViewControls";
import { plural } from "../../../lib/plural";
import { KitDefinitionEditor } from "../../inventory/KitChecklist";
import { capabilityOn, featureEnabled } from "../../../lib/features";
import { useReorderSuggestions } from "./ReorderSuggestions";
import { invalidateInventoryViews } from "../queryInvalidation";
import { useDomainSettingsDialog } from "../useDomainSettingsDialog";
import { MakerspaceLoanPolicySettings } from "../MakerspaceLoanPolicySettings";
import { LoanReservationPolicySettings } from "../LoanReservationPolicySettings";
import { categoryResults, type CategoryListResponse, type Makerspace, useStaffGet } from "./shared";
import {
  adjustPayload,
  defaultToBuyQuantity,
  emptyAdjust,
  emptyForm,
  formFromProduct,
  payloadFromForm,
  type AdjustmentForm,
  type AdminProduct,
  type ItemForm,
} from "./InventoryPanelShared";
import {
  IndividualAssets,
  ItemModal,
} from "./InventoryPanelParts";

export function Inventory({ makerspace, canViewAudit = false, canUseToBuy = false, canEditInventory = false }: { makerspace: Makerspace; canViewAudit?: boolean; canUseToBuy?: boolean; canEditInventory?: boolean }) {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const kitEnabled = featureEnabled(makerspace.enabled_features ?? [], "loans.kit_checklist");
  const list = useUrlListState({ id: "", q: "", ordering: "name", page: "1", archived: "false", low_stock: "false", out_of_stock: "false" });
  const search = list.values.q;
  const [selectedIds, setSelectedIds] = useState<Key[]>([]);
  const [form, setForm] = useState<ItemForm>(emptyForm);
  const [adjustForm, setAdjustForm] = useState<AdjustmentForm>(emptyAdjust);
  const [editing, setEditing] = useState<AdminProduct | null>(null);
  const [toBuyTarget, setToBuyTarget] = useState<AdminProduct | null>(null);
  const [toBuyQty, setToBuyQty] = useState("1");
  const [toBuyMessage, setToBuyMessage] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  // The loan policy (loan period, renewals, limits) belongs to the Inventory Manager, not only the Space Manager.
  const domainSettings = useDomainSettingsDialog(makerspace.id, "inventory", canEditInventory,
    (makerspace.enabled_modules ?? []).includes("request_workflow") ? <><MakerspaceLoanPolicySettings makerspaceId={makerspace.id} enabledFeatures={makerspace.enabled_features ?? []} />
      {["loans.pickup_windows", "loans.reservations", "loans.waitlist"].some(key => capabilityOn(makerspace, key)) ? <LoanReservationPolicySettings makerspaceId={makerspace.id} /> : null}</> : undefined,
    (makerspace.enabled_modules ?? []).includes("public_site"));
  useQuickCreate("item", () => { setForm(emptyForm); setAddOpen(true); });
  const [fixTarget, setFixTarget] = useState<AdminProduct | null>(null);
  const [assetFixTarget, setAssetFixTarget] = useState<AdminProduct | null>(null);
  const [fixQty, setFixQty] = useState("1");
  const [qrConfirm, setQrConfirm] = useState<boolean | null>(null);
  const [bulkQrMessage, setBulkQrMessage] = useState("");
  const showArchived = list.values.archived === "true";
  const showLowStock = list.values.low_stock === "true";
  const outOfStock = list.values.out_of_stock === "true";
  const archivedFilter = list.values.archived === "all" ? "all" : String(showArchived);
  const debouncedSearch = useDebouncedValue(search);
  useEffect(() => {
    setSelectedIds([]);
    setForm(emptyForm);
    setAdjustForm(emptyAdjust);
    setEditing(null);
    setToBuyTarget(null);
    setToBuyQty("1");
    setToBuyMessage("");
    setAddOpen(false);
    setFixTarget(null);
    setAssetFixTarget(null);
    setFixQty("1");
    setQrConfirm(null);
    setBulkQrMessage("");
  }, [makerspace.id]);
  const lowStockParam = `${showLowStock ? "&low_stock=true" : ""}${outOfStock ? "&out_of_stock=true" : ""}`;
  const inventoryQuery = `/admin/makerspace/${makerspace.id}/inventory?page=${list.page}&id=${encodeURIComponent(list.values.id)}&ordering=${encodeURIComponent(list.values.ordering)}&archived=${archivedFilter}&q=${encodeURIComponent(debouncedSearch)}${lowStockParam}`;
  const products = useStaffGet<{ count: number; results: AdminProduct[] }>(["inventory", makerspace.id, archivedFilter, showLowStock ? "low" : "all", outOfStock, debouncedSearch, list.page, list.values.ordering, list.values.id], inventoryQuery);
  useEffect(() => { setSelectedIds([]); }, [makerspace.id, list.query]);
  const categories = useStaffGet<CategoryListResponse>(["categories", makerspace.id], `/admin/makerspace/${makerspace.id}/categories`);
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["reorder-suggestions", makerspace.id] });
    invalidateInventoryViews(queryClient, makerspace.id, makerspace.slug);
    queryClient.invalidateQueries({ queryKey: ["categories", makerspace.id] });
  };
  const create = useMutation({
    mutationFn: () => staffRequest<AdminProduct>(`/admin/makerspace/${makerspace.id}/inventory`, { method: "POST", body: JSON.stringify(payloadFromForm(form, true)) }),
    // Reopen the just-created item in the edit modal so the user can add a photo.
    // The image uploader needs an existing product id, so it can't live on the add
    // form - this hands off straight into editing instead of forcing a manual re-open.
    onSuccess: (created) => { setAddOpen(false); invalidate(); openEdit(created); toast(t`Item created. Add a photo so members can recognise it.`); },
  });
  const update = useMutation({
    mutationFn: () => editing ? staffRequest(`/admin/inventory/${editing.id}`, { method: "PATCH", body: JSON.stringify(payloadFromForm(form, false)) }) : Promise.resolve(),
    onSuccess: () => { closeEdit(); setAdjustForm(emptyAdjust); invalidate(); },
  });
  const adjust = useMutation({
    mutationFn: () => editing ? staffRequest(`/admin/inventory/${editing.id}/adjust-quantity`, { method: "POST", body: JSON.stringify(adjustPayload(adjustForm)) }) : Promise.resolve(),
    onSuccess: () => { setAdjustForm(emptyAdjust); invalidate(); },
  });
  const { archive, unarchive } = useInventoryArchive(invalidate, () => {});
  const moveToFix = useMutation({
    mutationFn: () => {
      if (!fixTarget) return Promise.reject(new Error(t`Select an item first.`));
      return staffRequest(`/admin/inventory/${fixTarget.id}/needs-fix`, {
        method: "POST",
        body: JSON.stringify({ action: "shelve", quantity: Number(fixQty) || 1 }),
      });
    },
    onSuccess: () => {
      setFixTarget(null);
      setFixQty("1");
      queryClient.invalidateQueries({ queryKey: ["needs-fix-shelf", makerspace.id] });
      invalidate();
    },
  });
  const bulkQr = useMutation({
    mutationFn: async (enabled: boolean) => {
      const ids = [...selectedIds];
      const results = await Promise.allSettled(
        ids.map((id) =>
          staffRequest(`/admin/inventory/${String(id)}`, {
            method: "PATCH",
            body: JSON.stringify({ public_self_checkout_enabled: enabled }),
          }),
        ),
      );
      return {
        total: ids.length,
        succeeded: results.filter((result) => result.status === "fulfilled").length,
        failed: results.filter((result) => result.status === "rejected").length,
      };
    },
    onSuccess: (result) => {
      setQrConfirm(null);
      setBulkQrMessage(t`${result.succeeded} of ${result.total} items updated. ${result.failed} failed.`);
      invalidate();
    },
  });
  // Export the current view: selected rows when any are checked, else every row
  // matching the active filters (archived/search/low-stock).
  const exportInventory = useMutation({
    mutationFn: (format: "csv" | "xlsx") => {
      const base = `/admin/makerspace/${makerspace.id}/inventory/export?format=${format}`;
      const query = selectedIds.length
        ? `${base}&ids=${selectedIds.map((id) => String(id)).join(",")}`
        : `${base}&archived=${archivedFilter}&q=${encodeURIComponent(debouncedSearch)}${lowStockParam}`;
      return downloadStaffFile(query, `inventory-${makerspace.slug}.${format}`);
    },
  });
  const openFix = (product: AdminProduct) => {
    if (product.tracking_mode === "individual") {
      setAssetFixTarget(product);
      return;
    }
    setFixTarget(product);
    setFixQty(product.available_quantity > 0 ? "1" : "0");
  };
  const openToBuy = (product: AdminProduct) => {
    setToBuyTarget(product);
    setToBuyQty(defaultToBuyQuantity(product));
    setToBuyMessage("");
  };
  const toBuy = useMutation({
    mutationFn: () => {
      if (!toBuyTarget) {
        return Promise.reject(new Error(t`Select an item first.`));
      }
      return staffRequest(`/procurement/makerspace/${makerspace.id}/to-buy`, {
        method: "POST",
        body: JSON.stringify({ name: toBuyTarget.name, quantity: Number(toBuyQty) || 1, link: "", estimated_unit_cost: "" }),
      });
    },
    onSuccess: () => {
      setToBuyMessage(toBuyTarget ? t`${toBuyTarget.name} added to To buy.` : t`Item added to To buy.`);
      setToBuyTarget(null);
      setToBuyQty("1");
      queryClient.invalidateQueries({ queryKey: ["procurement", makerspace.id] });
    },
  });
  const rows = useMemo(() => products.data?.results ?? [], [products.data?.results]);
  const categoryRows = categoryResults(categories.data);
  const itemId = params.get("item") ?? "";
  const linkedItem = useStaffGet<{ results: AdminProduct[] }>(["inventory", makerspace.id, "item", itemId],
    `/admin/makerspace/${makerspace.id}/inventory?id=${encodeURIComponent(itemId)}&archived=all`, Boolean(itemId) && !rows.some(row => String(row.id) === itemId));
  const openEdit = (product: AdminProduct) => {
    setEditing(product);
    setParams(current => { current.set("item", String(product.id)); return current; });
    setForm({ ...formFromProduct(product), ...(kitEnabled ? { kit_components: product.kit_components ?? [] } : {}) });
    setAdjustForm(emptyAdjust);
  };
  const closeEdit = () => { setEditing(null); setParams(current => { current.delete("item"); current.delete("itemTab"); return current; }); };
  useEffect(() => {
    const id = params.get("item");
    if (!id) { setEditing(null); return; }
    const item = rows.find(row => String(row.id) === id) ?? linkedItem.data?.results.find(row => String(row.id) === id);
    if (item && editing?.id !== item.id) { setEditing(item); setForm({ ...formFromProduct(item), ...(kitEnabled ? { kit_components: item.kit_components ?? [] } : {}) }); }
    else if (item && item !== editing) setEditing(item);
  }, [params, rows, linkedItem.data, editing, kitEnabled]);
  const reorder = useReorderSuggestions({ makerspaceId: makerspace.id, canProcure: canUseToBuy });
  const selectedSuffix = selectedIds.length ? ` (${selectedIds.length} selected)` : "";
  const columns = inventoryColumns({ openEdit, openFix, openToBuy, archive: item => archive.mutate(item), unarchive: item => unarchive.mutate(item), canUseToBuy, pending: archive.isPending || unarchive.isPending, stockTab: showLowStock || outOfStock });
  const addItem = { label: t`Add item`, onClick: () => { setForm(emptyForm); setAddOpen(true); } };
  const href = (archived: string, low: string, out: string) => { const next = new URLSearchParams(params); next.set("archived", archived); next.set("low_stock", low); next.set("out_of_stock", out); next.delete("page"); return `?${next}`; };
  const activeTab = showArchived ? "archived" : outOfStock ? "out" : showLowStock ? "low" : "all";
  if (addOpen) return <ItemModal title={t`Add item`} open onClose={() => setAddOpen(false)} form={form} setForm={setForm} categories={categoryRows} makerspace={makerspace} includeQuantities pending={create.isPending} error={create.error?.message} onSubmit={() => create.mutate()}>
    {kitEnabled ? <KitDefinitionEditor value={form.kit_components ?? []} onChange={value => setForm(current => ({ ...current, kit_components: value }))} /> : null}
  </ItemModal>;
  return (
    <ListLayout width="wide" header={{ title: t`Inventory`, subtitle: t`Parts, tools and the stock ready for your next project.`, primary: addItem,
      secondary: { label: t`Export`, menu: [{ label: t`Export CSV${selectedSuffix}`, pending: exportInventory.isPending, onClick: () => exportInventory.mutate("csv") }, { label: t`Export Excel${selectedSuffix}`, pending: exportInventory.isPending, onClick: () => exportInventory.mutate("xlsx") }] }, overflow: domainSettings.actions.length ? domainSettings.actions : undefined, meta: plural(products.data?.count ?? 0, "item") }}
      callout={reorder.callout} state={inventoryQueryState(products, "inventory")} isEmpty={!rows.length} filtered={Boolean(search || showArchived || showLowStock || outOfStock || list.values.id)}
      empty={{ message: t`No parts added yet. Add your first item.`, action: addItem }} filteredEmpty={{ message: showArchived ? t`No archived items.` : showLowStock ? t`Nothing low on stock.` : t`Nothing matches these filters.`, action: { label: t`Clear filters`, onClick: () => list.restore({}) } }}
      tabs={[{ key: "all", label: t`All`, href: href("false", "false", "false") }, { key: "low", label: t`Low stock`, href: href("false", "true", "false") }, { key: "out", label: t`Out of stock`, href: href("false", "false", "true") }, { key: "archived", label: t`Archived`, href: href("true", "false", "false") }]} activeTab={activeTab}
      filters={{ toolbar: <ListViewControls state={list} makerspaceId={makerspace.id} entity="inventory" searchLabel="Search inventory"
        sorts={[["name", "Name"], ["-name", "Name descending"], ["available_quantity", "Available first"], ["-available_quantity", "Available last"]]} /> }}
      bulkBar={{ count: selectedIds.length, onClear: () => setSelectedIds([]), actions: [{ label: t`Enable QR`, pending: bulkQr.isPending, onClick: () => { setBulkQrMessage(""); setQrConfirm(true); } }, { label: t`Disable QR`, pending: bulkQr.isPending, onClick: () => { setBulkQrMessage(""); setQrConfirm(false); } }, { label: t`Export CSV`, pending: exportInventory.isPending, onClick: () => exportInventory.mutate("csv") }, { label: t`Export Excel`, pending: exportInventory.isPending, onClick: () => exportInventory.mutate("xlsx") }] }}
      body={{ kind: "table", table: <DataTable<AdminProduct> listState={list} ordering={list.values.ordering} onOrderingChange={value => list.setFilter("ordering", value)} columns={columns} data={rows} getRowId={row => row.id} selectedIds={selectedIds} onSelectionChange={setSelectedIds} /> }}
      pagination={{ page: list.page, pageSize: 24, count: products.data?.count ?? 0, onChange: list.setPage }}
      detail={<>
      {reorder.panel}{products.isError ? null : reorder.error}
      <p role="status" className="text-sm text-muted">{toBuyMessage || bulkQrMessage}</p><ErrorText message={exportInventory.error?.message} />
      {editing ? <InventoryItemDetail product={editing} makerspace={makerspace} canViewAudit={canViewAudit} kitEnabled={kitEnabled} form={form} setForm={setForm} categories={categoryRows} onClose={closeEdit}
        pending={update.isPending} error={update.error?.message} onSave={() => update.mutate()} onArchive={() => { archive.mutate(editing); closeEdit(); }}
        adjustForm={adjustForm} setAdjustForm={setAdjustForm} adjustPending={adjust.isPending} adjustError={adjust.error?.message} onAdjust={() => adjust.mutate()} invalidate={invalidate} /> : itemId ? <DetailLayout presentation="drawer" open onClose={closeEdit} title={t`Inventory item`} state={inventoryQueryState(linkedItem, "this item")} isEmpty={!linkedItem.data?.results.length} empty={{ message: t`This item isn't available in this makerspace. Close this drawer to return to inventory.` }} main={null} /> : null}
      {canUseToBuy ? (
        <Modal open={Boolean(toBuyTarget)} onClose={() => setToBuyTarget(null)} title={t`Add to To buy`} footer={<div className="desk-actions flex flex-wrap justify-end gap-2"><button className="desk-button-ghost" type="button" disabled={toBuy.isPending} onClick={() => setToBuyTarget(null)}>{t`Cancel`}</button><button className="desk-button-primary" type="button" disabled={toBuy.isPending} onClick={() => toBuy.mutate()}>{toBuy.isPending ? t`Adding…` : t`Add`}</button></div>}>
          <div className="grid gap-3 text-sm">
            <p className="font-semibold text-ink">{toBuyTarget?.name}</p>
            <Field label={t`Quantity`}><QuantityStepper label="quantity" min={1} value={toBuyQty} onValueChange={setToBuyQty} /></Field>
            {toBuy.error ? <p className="text-sm text-danger">{toBuy.error.message}</p> : null}
          </div>
        </Modal>
      ) : null}
      <Modal open={Boolean(fixTarget)} onClose={() => setFixTarget(null)} title={t`Move to repair shelf`} footer={<div className="desk-actions flex flex-wrap justify-end gap-2"><button className="desk-button-ghost" type="button" disabled={moveToFix.isPending} onClick={() => setFixTarget(null)}>{t`Cancel`}</button><button className="desk-button-warn" type="button" disabled={moveToFix.isPending || !fixTarget || Number(fixQty) < 1 || Number(fixQty) > (fixTarget?.available_quantity ?? 0)} onClick={() => moveToFix.mutate()}>{moveToFix.isPending ? t`Moving…` : t`Move to repair shelf`}</button></div>}>
        <div className="grid gap-3 text-sm">
          <p className="font-semibold text-ink">{fixTarget?.name}</p>
          <p className="text-muted">{t`Move available units out of circulation for repair.`}</p>
          <Field label={t`Quantity (${fixTarget?.available_quantity ?? 0} available)`}><QuantityStepper label="quantity" min={1} max={fixTarget?.available_quantity ?? 1} value={fixQty} onValueChange={setFixQty} /></Field>
          {moveToFix.error ? <p className="text-sm text-danger">{moveToFix.error.message}</p> : null}
        </div>
      </Modal>
      <Modal open={Boolean(assetFixTarget)} onClose={() => setAssetFixTarget(null)} title={assetFixTarget ? t`Choose an asset to repair · ${assetFixTarget.name}` : t`Choose an asset to repair`} footer={<div className="desk-actions flex flex-wrap justify-end gap-2"><button className="desk-button-ghost" type="button" onClick={() => setAssetFixTarget(null)}>{t`Close`}</button></div>}>
        {assetFixTarget ? <IndividualAssets productId={assetFixTarget.id} makerspaceId={makerspace.id} refreshInventory={invalidate} /> : null}
      </Modal>
      {domainSettings.dialog}
      <ConfirmDialog open={qrConfirm !== null} title={qrConfirm ? t`Enable public QR` : t`Disable public QR`} message={t`${qrConfirm ? "Enable" : "Disable"} public self-checkout QR for ${selectedIds.length} selected items?`} confirmLabel={qrConfirm ? t`Enable` : t`Disable`} pending={bulkQr.isPending} onCancel={() => setQrConfirm(null)} onConfirm={() => { if (qrConfirm !== null) bulkQr.mutate(qrConfirm); }} />
      </>} />
  );
}
