import { t } from "@lingui/core/macro";
import { useSearchParams } from "react-router-dom";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { downloadStaffFile, staffRequest } from "../../../lib/api";
import { type Makerspace, type Product, useStaffGet } from "./shared";
import { invalidateInventoryViews, invalidateQrViews } from "../queryInvalidation";

type ListResponse<T> = { results: T[] };
type QrCode = { id: number; payload: string; target_type: string; target_id: number };
type AssetRow = { id: number; asset_tag: string; serial_number: string; status: string; box_label: string | null; qr_code_id: number | null; qr_payload: string | null };
type Batch = { id: number; title: string; status: string; created_at: string };
type BatchItem = { id: number; qr_code: QrCode; label_text: string; target_type: string; target_id: number };
type BatchDetail = Batch & { items: BatchItem[] };

export function useQrBatchBuilder({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const batchId = params.get("batch") ?? "";
  const setBatchId = (id: string, replace = false) => setParams(current => { if (id) current.set("batch", id); else current.delete("batch"); return current; }, { replace });
  const [labelMode, setLabelMode] = useState("item");
  const [batchTitle, setBatchTitle] = useState("QR labels");
  const [productId, setProductId] = useState("");
  const [assetId, setAssetId] = useState("");
  const [assetCount, setAssetCount] = useState("50");
  const [assetPrefix, setAssetPrefix] = useState("");
  const [batchModalOpen, setBatchModalOpen] = useState(false);
  const batches = useStaffGet<ListResponse<Batch>>(["qr-batches", makerspace.id], `/admin/makerspace/${makerspace.id}/qr-print-batches`);
  const products = useStaffGet<ListResponse<Product>>(["inventory", makerspace.id], `/admin/makerspace/${makerspace.id}/inventory?page_size=1000`);
  // Opening QR labels continues the most recent batch, as before the revamp. Only once per visit, so
  // "All batches" still shows the list instead of bouncing straight back into a batch.
  const autoSelected = useRef(Boolean(batchId));
  const latestBatchId = batches.data?.results?.[0]?.id;
  useEffect(() => {
    if (autoSelected.current || latestBatchId === undefined) return;
    autoSelected.current = true;
    if (!batchId) setBatchId(String(latestBatchId), true);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- first load only: batchId and setBatchId are read, not tracked, so choosing 'All batches' does not bounce back into a batch
  }, [latestBatchId]); // first load only: setBatchId and batchId are deliberately read, not tracked
  const activeBatchId = Number(batchId) || 0;
  const selectedProductId = Number(productId) || 0;
  const batch = useStaffGet<BatchDetail>(["qr-batch", activeBatchId], `/admin/qr-print-batches/${activeBatchId}`, Boolean(activeBatchId));

  const productOptions = useMemo(() => products.data?.results?.filter((product) => !product.is_archived) ?? [], [products.data]);
  const selectedProduct = useMemo(
    () => productOptions.find((product) => product.id === selectedProductId),
    [selectedProductId, productOptions],
  );
  const selectedIsIndividual = selectedProduct?.tracking_mode === "individual";
  const assets = useStaffGet<ListResponse<AssetRow>>(
    ["inventory-assets", selectedProductId],
    `/admin/inventory/${selectedProductId}/assets`,
    Boolean(selectedIsIndividual && selectedProductId),
  );

  const refreshBatch = () => {
    queryClient.invalidateQueries({ queryKey: ["qr-batches", makerspace.id] });
    if (activeBatchId) queryClient.invalidateQueries({ queryKey: ["qr-batch", activeBatchId] });
  };
  const createBatch = useMutation({
    mutationFn: () =>
      staffRequest<Batch>(`/admin/makerspace/${makerspace.id}/qr-print-batches`, {
        method: "POST",
        body: JSON.stringify({ title: batchTitle.trim() }),
      }),
    onSuccess: (created) => {
      setBatchId(String(created.id));
      setBatchModalOpen(false);
      refreshBatch();
    },
  });
  const addItem = async (qrCodeId: number, labelText: string) => {
    await staffRequest(`/admin/qr-print-batches/${activeBatchId}/items`, {
      method: "POST",
      body: JSON.stringify({ qr_code_id: qrCodeId, label_text: labelText }),
    });
  };
  const addProduct = useMutation({
    mutationFn: async () => {
      if (!selectedProduct) throw new Error(t`Choose an inventory item.`);
      if (selectedProduct.tracking_mode === "individual") throw new Error(t`Generate unit QRs for individual inventory.`);
      const qr = await staffRequest<QrCode>("/admin/qr/tools", {
        method: "POST",
        body: JSON.stringify({ makerspace_id: makerspace.id, product_id: selectedProduct.id }),
      });
      await addItem(qr.id, selectedProduct.name);
    },
    onSuccess: refreshBatch,
  });
  const reprintAsset = useMutation({
    mutationFn: async () => {
      const asset = assets.data?.results?.find((item) => item.id === Number(assetId));
      if (!asset) throw new Error(t`Choose an existing unit.`);
      const qr = await staffRequest<QrCode>(`/admin/assets/${asset.id}/qr`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      await addItem(qr.id, asset.asset_tag);
    },
    onSuccess: () => {
      invalidateInventoryViews(queryClient, makerspace.id);
      invalidateQrViews(queryClient, makerspace.id);
      queryClient.invalidateQueries({ queryKey: ["inventory-assets", selectedProductId] });
      refreshBatch();
    },
  });
  const generateAssets = useMutation({
    mutationFn: () => {
      if (!selectedProduct) return Promise.reject(new Error(t`Choose an inventory item.`));
      return staffRequest(`/admin/products/${selectedProduct.id}/assets/generate`, {
        method: "POST",
        body: JSON.stringify({
          count: Number(assetCount),
          name_prefix: assetPrefix.trim() || selectedProduct.name,
          print_batch_id: activeBatchId,
        }),
      });
    },
    onSuccess: () => {
      invalidateInventoryViews(queryClient, makerspace.id);
      invalidateQrViews(queryClient, makerspace.id);
      queryClient.invalidateQueries({ queryKey: ["inventory-assets", selectedProductId] });
      refreshBatch();
    },
  });
  const downloadZip = useMutation({
    mutationFn: () =>
      downloadStaffFile(
        `/admin/qr-print-batches/${activeBatchId}/download`,
        `qr-batch-${activeBatchId}.zip`,
      ),
  });
  const hasBatch = Boolean(activeBatchId);
  // Both unit-QR endpoints (`assets/generate` and the per-asset reprint) are guarded by
  // `asset_units` on the backend, so offering the controls without it produces a form
  // whose only outcome is a 404. An empty list means "not loaded", never "none enabled".
  const modules = makerspace.enabled_modules ?? [];
  const assetUnitsEnabled = modules.length === 0 || modules.includes("asset_units");
  const batchItems = batch.data?.items ?? [];
  const count = Number(assetCount);
  const assetOptions = assets.data?.results ?? [];
  const canGenerateAssets = hasBatch && Boolean(selectedProduct) && selectedIsIndividual && Number.isInteger(count) && count > 0 && count <= 200;
  const canReprintAsset = hasBatch && selectedIsIndividual && Boolean(assetId);
  const canAddItemQr = hasBatch && Boolean(selectedProduct) && !selectedIsIndividual;
  const selectProduct = (nextId: string) => {
    setProductId(nextId);
    setAssetId("");
    const product = productOptions.find((item) => item.id === Number(nextId));
    setAssetPrefix(product?.name ?? "");
  };

  return {
    batchId, setBatchId, batchModalOpen, setBatchModalOpen, batchTitle,
    setBatchTitle, batches, createBatch, batch, batchItems,
    downloadZip, labelMode, setLabelMode, productId, setProductId, selectProduct,
    productOptions, hasBatch, products, selectedProduct, selectedIsIndividual,
    assetUnitsEnabled, assetCount, setAssetCount, assetPrefix, setAssetPrefix,
    canGenerateAssets, generateAssets, assetId, setAssetId, assets,
    assetOptions, canReprintAsset, reprintAsset, canAddItemQr, addProduct,
  };
}
