import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { stocktakeConditionLabel } from "../lifecycleLabels";
import { DataTable, EmptyState, ErrorBlock, ScanWorkbench, Skeleton, StatRow, StatusPill } from "../../../components/ui";
import { type Makerspace, useStaffGet } from "./shared";
import { QuantityStepper } from "../QuantityStepper";

type StocktakeRow = { id: number; status: string; notes: string; container: number | null };
type StocktakeLine = {
  id: number;
  product: number | null;
  asset: number | null;
  expected_quantity: number | null;
  counted_quantity: number;
  variance_quantity: number | null;
  condition: string;
  container: number | null;
  notes: string;
};
type StocktakeDetail = StocktakeRow & { blind?: boolean; lines: StocktakeLine[] };
type ProductOption = { id: number; name: string; tracking_mode: string };
type ContainerOption = { id: number; label: string; location?: string };
type AssetOption = { id: number; asset_tag: string; serial_number: string; status: string };
type StocktakeScanResult = {
  type: "box" | "asset" | "product";
  container_id?: number;
  asset_id?: number;
  product_id?: number;
  label?: string;
  asset_tag?: string;
  name?: string;
};

const CONDITIONS = ["available", "damaged", "lost", "unknown"];

// The count step is what moves a stocktake forward and produces the variance the Apply
// step adjusts on - without it a stocktake has zero lines and Apply is a no-op. Records
// a counted quantity per product, then shows expected/counted/variance from the detail.
export function CountSection({ makerspace, stocktakeId, readOnly = false }: { makerspace: Makerspace; stocktakeId: number; readOnly?: boolean }) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"product" | "asset">("product");
  const [productId, setProductId] = useState("");
  const [assetId, setAssetId] = useState("");
  const [containerId, setContainerId] = useState("");
  const [counted, setCounted] = useState("0");
  const [condition, setCondition] = useState("available");
  const [notes, setNotes] = useState("");
  const [scanNote, setScanNote] = useState("");
  const detail = useStaffGet<StocktakeDetail>(["stocktake-detail", stocktakeId], `/admin/stocktakes/${stocktakeId}`);
  const products = useStaffGet<{ results: ProductOption[] }>(["inventory-all", makerspace.id], `/admin/makerspace/${makerspace.id}/inventory?page_size=1000`);
  const containers = useStaffGet<{ results: ContainerOption[] }>(["stocktake-containers", makerspace.id], `/admin/makerspace/${makerspace.id}/containers?page_size=1000`);
  const assets = useStaffGet<{ results: AssetOption[] }>(["stocktake-assets", productId], productId ? `/admin/inventory/${productId}/assets?page_size=1000` : "", Boolean(productId));
  const productName = (id: number | null) => products.data?.results.find((product) => product.id === id)?.name ?? (id ? `#${id}` : "-");
  const assetName = (id: number | null) => assets.data?.results.find((asset) => asset.id === id)?.asset_tag ?? (id ? `Asset #${id}` : "-");
  const containerName = (id: number | null) => containers.data?.results.find((container) => container.id === id)?.label ?? (id ? `Container #${id}` : "-");

  const record = useMutation({
    mutationFn: () => {
      const payload = {
        ...(mode === "asset" ? { asset_id: Number(assetId) } : { product_id: Number(productId) }),
        ...(containerId ? { container_id: Number(containerId) } : {}),
        counted_quantity: Number(counted) || 0,
        condition,
        notes,
      };
      return staffRequest(`/admin/stocktakes/${stocktakeId}/count-lines`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      setProductId("");
      setAssetId("");
      setContainerId("");
      setCounted("0");
      setNotes("");
      queryClient.invalidateQueries({ queryKey: ["stocktake-detail", stocktakeId] });
      queryClient.invalidateQueries({ queryKey: ["stocktakes", makerspace.id] });
    },
  });
  const handleScan = async (payload: string) => {
    try {
      const result = await staffRequest<StocktakeScanResult>(`/admin/stocktakes/${stocktakeId}/resolve-scan`, {
        method: "POST",
        body: JSON.stringify({ payload }),
      });
      if (result.type === "asset" && result.asset_id && result.product_id) {
        setMode("asset");
        setProductId(String(result.product_id));
        setAssetId(String(result.asset_id));
      } else if (result.type === "product" && result.product_id) {
        setMode("product");
        setProductId(String(result.product_id));
        setAssetId("");
      } else if (result.type === "box" && result.container_id) {
        setContainerId(String(result.container_id));
      }
      setScanNote(`Scanned ${result.asset_tag || result.name || result.label || payload}`);
    } catch (error) {
      setScanNote(error instanceof Error ? error.message : "Unable to resolve scanned QR");
    }
  };
  const recordError = record.error instanceof Error ? record.error.message : undefined;
  const lines = detail.data?.lines ?? [];
  const editable = !readOnly && ["draft", "counting"].includes(detail.data?.status ?? "");
  const canSave = editable && (mode === "asset" ? Boolean(assetId) : Boolean(productId));

  return (
    <div className="mt-3 rounded-md border border-line bg-bg p-3">
      {detail.isLoading ? <Skeleton className="h-32" /> : detail.error ? <ErrorBlock error={detail.error} resource={t`the count`} onRetry={() => { void detail.refetch(); }} /> : null}
      {editable ? <ScanWorkbench searchLabel="QR payload" onFind={handleScan} onScan={handleScan}
        controls={<div className="@container grid gap-3">
      {/* Sized by the workbench column, not the viewport: beside the camera at xl the column is half width. */}
      <div className="grid gap-3 @lg:grid-cols-2 @4xl:grid-cols-[8rem_minmax(0,1fr)_minmax(0,1fr)_12rem_9rem] @lg:items-end">
        <label className="eyebrow grid gap-1">
          <span>{t`Count type`}</span>
          <select className="desk-input" value={mode} onChange={(event) => { setMode(event.target.value as "product" | "asset"); setAssetId(""); }}>
            <option value="product">{t`Product`}</option>
            <option value="asset">{t`Asset`}</option>
          </select>
        </label>
        <label className="eyebrow grid gap-1">
          <span>{mode === "asset" ? t`Product for asset` : t`Product`}</span>
          <select className="desk-input" value={productId} disabled={products.isLoading} onChange={(event) => { setProductId(event.target.value); setAssetId(""); }}>
            <option value="">{t`Select product`}</option>
            {products.data?.results.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
          </select>
        </label>
        {mode === "asset" ? (
          <label className="eyebrow grid gap-1">
            <span>{t`Asset`}</span>
            <select className="desk-input" value={assetId} disabled={!productId || assets.isLoading} onChange={(event) => setAssetId(event.target.value)}>
              <option value="">{t`Select asset`}</option>
              {assets.data?.results.map((asset) => <option key={asset.id} value={asset.id}>{asset.asset_tag}{detail.data?.blind ? "" : ` (${asset.status})`}</option>)}
            </select>
          </label>
        ) : (
          <label className="eyebrow grid gap-1">
            <span>{t`Line container`}</span>
            <select className="desk-input" value={containerId} onChange={(event) => setContainerId(event.target.value)}>
              <option value="">{t`No container`}</option>
              {containers.data?.results.map((container) => <option key={container.id} value={container.id}>{container.label}</option>)}
            </select>
          </label>
        )}
        <label className="eyebrow grid gap-1">
          <span>{t`Counted`}</span>
          <QuantityStepper label="counted" value={counted} onValueChange={setCounted} />
        </label>
        <label className="eyebrow grid gap-1">
          <span>{t`Condition`}</span>
          <select className="desk-input" value={condition} onChange={(event) => setCondition(event.target.value)}>
            {CONDITIONS.map((value) => <option key={value} value={value}>{stocktakeConditionLabel(value)}</option>)}
          </select>
        </label>
      </div>
      {mode === "asset" ? (
        <label className="eyebrow mt-2 grid gap-1">
          <span>{t`Line container`}</span>
          <select className="desk-input" value={containerId} onChange={(event) => setContainerId(event.target.value)}>
            <option value="">{t`No container`}</option>
            {containers.data?.results.map((container) => <option key={container.id} value={container.id}>{container.label}</option>)}
          </select>
        </label>
      ) : null}
      <label className="eyebrow mt-2 grid gap-1">
        <span>{t`Line notes`}</span>
        <input className="desk-input" value={notes} onChange={(event) => setNotes(event.target.value)} />
      </label>
      <div className="desk-actions mt-2 flex flex-wrap gap-2">
        <button className="desk-button-primary w-full @md:w-auto" disabled={!canSave || record.isPending || readOnly} onClick={() => record.mutate()}>{record.isPending ? t`Saving…` : t`Record count`}</button>
      </div>
        </div>} /> : null}
      {scanNote ? <p className={`mt-2 text-sm ${scanNote.startsWith("Scanned ") ? "text-muted" : "text-danger"}`}>{scanNote}</p> : null}
      {recordError ? <p className="mt-2 text-sm text-danger">{recordError}</p> : null}
      <StatRow stats={[{ label: t`Lines counted`, value: lines.length }, ...(!detail.data?.blind ? [{ label: t`Variances`, value: lines.filter(line => line.variance_quantity != null && line.variance_quantity !== 0).length }] : [])]} />
      <h2 className="title-section mt-6">{t`Counted so far`}</h2>
      {lines.length ? <DataTable<StocktakeLine> data={lines} getRowId={line => line.id} columns={[
        { key: "item", header: t`Item`, render: line => line.asset ? assetName(line.asset) : productName(line.product) },
        { key: "container", header: t`Container`, render: line => containerName(line.container) },
        { key: "expected_quantity", header: t`Expected`, render: line => line.expected_quantity ?? "Hidden" },
        { key: "counted_quantity", header: t`Counted` },
        { key: "variance_quantity", header: t`Variance`, render: line => <StatusPill label={line.variance_quantity === null ? t`Hidden` : String(line.variance_quantity)} tone={line.variance_quantity ? "warn" : "neutral"} /> },
        { key: "condition", header: t`Condition`, render: line => <StatusPill label={stocktakeConditionLabel(line.condition)} /> },
        { key: "notes", header: t`Notes` },
      ]} /> : <EmptyState message={t`No counts recorded yet. Scan or pick an item to start.`} />}

    </div>
  );
}

