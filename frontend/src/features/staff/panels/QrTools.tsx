import type React from "react";
import { ListLayout, DetailLayout } from "../../../components/layouts";
import { ErrorText, Field, Modal, EmptyState, ListRow, RelativeTime, SegmentedControl } from "../../../components/ui";
import { inventoryQueryState } from "./inventoryPresentation";
import { QrImage } from "./QrImage";
import { useQrBatchBuilder } from "./useQrBatchBuilder";
import type { Makerspace } from "./shared";
export function QrTools({ makerspace }: { makerspace: Makerspace }) {
 const {
   batchId, setBatchId, batchModalOpen, setBatchModalOpen, batchTitle,
   setBatchTitle, batches, createBatch, batch, batchItems,
   downloadZip, labelMode, setLabelMode, productId, setProductId, selectProduct,
   productOptions, hasBatch, products, selectedProduct, selectedIsIndividual,
   assetUnitsEnabled, assetCount, setAssetCount, assetPrefix, setAssetPrefix,
   canGenerateAssets, generateAssets, assetId, setAssetId, assets,
   assetOptions, canReprintAsset, reprintAsset, canAddItemQr, addProduct,
 } = useQrBatchBuilder({ makerspace });
  const createDialog = <>
      <Modal open={batchModalOpen} onClose={() => setBatchModalOpen(false)} title="Create QR print batch" footer={<ModalActions pending={createBatch.isPending} onCancel={() => setBatchModalOpen(false)} onSubmit={() => createBatch.mutate()} submitLabel="Create batch" disabled={!batchTitle.trim()} />}>
        <Field label="Batch title"><input className="desk-input w-full" value={batchTitle} onChange={(event) => setBatchTitle(event.target.value)} /></Field>
        {createBatch.isError ? <ErrorText message={createBatch.error.message} /> : null}
      </Modal>
  </>;
  if (!batchId) return <ListLayout header={{ title: "QR labels", subtitle: "Print labels for items, units and boxes.", primary: { label: "New batch", onClick: () => setBatchModalOpen(true) } }}
    state={inventoryQueryState(batches, "label batches")} isEmpty={!batches.data?.results.length}
    empty={{ message: "No label batches yet. Start one to print QR labels.", action: { label: "New batch", onClick: () => setBatchModalOpen(true) } }}
    body={{ kind: "rows", rows: batches.data?.results.map(item => <ListRow key={item.id} title={item.title} identity={{ kind: "date", date: item.created_at }} meta={<RelativeTime date={item.created_at} />} onClick={() => setBatchId(String(item.id))} />) }} detail={createDialog} />;
  return <DetailLayout title={batch.data?.title ?? "QR labels"} back={{ label: "All batches", onClick: () => setBatchId("") }} state={inventoryQueryState(batch, "this label batch")} meta={[`${batchItems.length} labels`]}
    actions={{ primary: { label: "Download all (ZIP)", pending: downloadZip.isPending, pendingLabel: "Preparing…", disabled: !batchItems.length, disabledReason: "Add a label to this batch first.", onClick: () => downloadZip.mutate() } }}
    main={<div className="grid gap-6">
        <ActionBox title="Add labels">
          <SegmentedControl label="Label type" value={labelMode} options={[{ value: "item", label: "Item" }, { value: "units", label: "Units" }, { value: "reprint", label: "Reprint a unit" }]} onChange={value => { setLabelMode(value); setProductId(""); setAssetId(""); }} />
          <Field label="Inventory item"><select className="desk-input w-full" value={productId} disabled={!hasBatch || products.isLoading} onChange={(event) => selectProduct(event.target.value)}>
            <option value="">Inventory item</option>
            {productOptions.filter(product => labelMode === "item" ? product.tracking_mode !== "individual" : product.tracking_mode === "individual").map((product) => (
              <option key={product.id} value={product.id}>
                {product.name} | {product.tracking_mode} | {product.available_quantity} available
              </option>
            ))}
          </select></Field>
          {selectedProduct ? <p className="mt-2 text-xs uppercase text-muted">{selectedProduct.tracking_mode}</p> : null}
          {selectedIsIndividual && !assetUnitsEnabled ? (
            <p className="mt-2 text-sm text-muted">
              Unit QR generation needs the Asset units module.
            </p>
          ) : null}
          {selectedIsIndividual && assetUnitsEnabled ? (
            <div className="mt-2 grid gap-3">
              {labelMode === "units" ? <div className="grid gap-2 sm:grid-cols-[110px_1fr_auto]">
                <Field label="Unit count"><input className="desk-input" inputMode="numeric" value={assetCount} onChange={(event) => setAssetCount(event.target.value)} /></Field>
                <Field label="Label prefix"><input className="desk-input" value={assetPrefix} onChange={(event) => setAssetPrefix(event.target.value)} /></Field>
                <button className="desk-button" type="button" disabled={!canGenerateAssets || generateAssets.isPending} onClick={() => generateAssets.mutate()}>
                  {generateAssets.isPending ? "Generating…" : "Generate missing/new unit QRs"}
                </button>
              </div> : null}
              {labelMode === "reprint" ? <div className="grid gap-2 border-t border-line pt-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                <Field label="Existing unit to reprint"><select className="desk-input w-full" value={assetId} disabled={!hasBatch || assets.isLoading} onChange={(event) => setAssetId(event.target.value)}>
                  <option value="">Existing unit to reprint</option>
                  {assetOptions.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.asset_tag} | {asset.status} | {asset.qr_code_id ? `QR #${asset.qr_code_id}` : "no QR linked"}
                    </option>
                  ))}
                </select></Field>
                <button className="desk-button" type="button" disabled={!canReprintAsset || reprintAsset.isPending} onClick={() => reprintAsset.mutate()}>
                  {reprintAsset.isPending ? "Adding…" : "Reprint unit QR"}
                </button>
              </div> : null}
              {assets.isLoading ? <p className="text-sm text-muted">Loading units…</p> : null}
              {assets.isError ? <ErrorText message={assets.error.message} /> : null}
              {!assets.isLoading && selectedProduct && !assetOptions.length ? <p className="text-sm text-muted">No individual units yet.</p> : null}
            </div>
          ) : null}
          {labelMode === "item" ? (
            <button className="desk-button mt-2" type="button" disabled={!canAddItemQr || addProduct.isPending} onClick={() => addProduct.mutate()}>
              {addProduct.isPending ? "Adding…" : "Add/reprint item QR"}
            </button>
          ) : null}
          {addProduct.isError ? <ErrorText message={addProduct.error.message} /> : null}
          {reprintAsset.isError ? <ErrorText message={reprintAsset.error.message} /> : null}
          {generateAssets.isError ? <ErrorText message={generateAssets.error.message} /> : null}
        </ActionBox>

        <div className="rounded-md border border-line bg-surface p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="title-section">Labels in this batch</h3>
              <p className="text-sm text-muted">{batchItems.length} QR labels accumulated</p>
            </div>

          </div>
          {batch.isLoading ? <p className="mt-3 text-sm text-muted">Loading batch…</p> : null}
          {batch.isError ? <ErrorText message={batch.error.message} /> : null}
          {!batch.isLoading && !batchItems.length ? <EmptyState message="This batch is empty. Add an item or units to start." /> : null}
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {batchItems.map((item) => (
              <article key={item.id} className="rounded-md border border-line bg-bg p-3 text-center">
                <QrImage qrId={item.qr_code.id} label={item.label_text} />
                <p className="mt-2 text-sm font-semibold text-ink">{item.label_text}</p>
                <p className="text-xs text-muted">{item.target_type} #{item.target_id}</p>
              </article>
            ))}
          </div>
          {downloadZip.isError ? <ErrorText message={(downloadZip.error as Error).message} /> : null}
        </div>

    </div>} />;
}

function ActionBox({ children, title }: { children: React.ReactNode; title: string }) {
  return <section className="rounded-md border border-line bg-surface p-3"><h3 className="title-section mb-2">{title}</h3>{children}</section>;
}

function ModalActions(props: { pending: boolean; disabled: boolean; submitLabel: string; onCancel: () => void; onSubmit: () => void }) {
  return (
    <div className="flex flex-wrap justify-end gap-2">
      <button className="desk-button-ghost" type="button" disabled={props.pending} onClick={props.onCancel}>Cancel</button>
      <button className="desk-button-primary" type="button" disabled={props.pending || props.disabled} onClick={props.onSubmit}>
        {props.pending ? "Saving…" : props.submitLabel}
      </button>
    </div>
  );
}
