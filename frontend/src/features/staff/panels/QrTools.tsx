import { t } from "@lingui/core/macro";
import type React from "react";
import { ListLayout, DetailLayout } from "../../../components/layouts";
import { ErrorText, Field, Modal, EmptyState, ListRow, RelativeTime, SegmentedControl } from "../../../components/ui";
import { inventoryQueryState } from "./inventoryPresentation";
import { QrImage } from "./QrImage";
import { QrLabelPrinterSend } from "./QrLabelPrinterSend";
import { useQrBatchBuilder } from "./useQrBatchBuilder";
import type { Makerspace } from "./shared";
import { LogoLoader } from "../../../components/LogoLoader";
import { BoxArt } from "../../../components/BoxSpinner";
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
  // The label adapter needs both modules (server: devices/label_access.MODULES).
  const labelPrintersOn = ["devices", "qr_print_batches"].every(key => (makerspace.enabled_modules ?? []).includes(key));
  const createDialog = <>
      <Modal open={batchModalOpen} onClose={() => setBatchModalOpen(false)} title={t`Create QR print batch`} footer={<ModalActions pending={createBatch.isPending} onCancel={() => setBatchModalOpen(false)} onSubmit={() => createBatch.mutate()} submitLabel={t`Create batch`} disabled={!batchTitle.trim()} />}>
        <Field label={t`Batch title`}><input className="desk-input w-full" value={batchTitle} onChange={(event) => setBatchTitle(event.target.value)} /></Field>
        {createBatch.isError ? <ErrorText message={createBatch.error.message} /> : null}
      </Modal>
  </>;
  if (!batchId) return <ListLayout header={{ title: t`QR labels`, subtitle: t`Print labels for items, units and boxes.`, primary: { label: t`New batch`, onClick: () => setBatchModalOpen(true) } }}
    state={inventoryQueryState(batches, "label batches")} isEmpty={!batches.data?.results.length}
    empty={{ message: t`No label batches yet. Start one to print QR labels.`, action: { label: t`New batch`, onClick: () => setBatchModalOpen(true) } }}
    body={{ kind: "rows", rows: batches.data?.results.map(item => <ListRow key={item.id} title={item.title} identity={{ kind: "date", date: item.created_at }} meta={<RelativeTime date={item.created_at} />} onClick={() => setBatchId(String(item.id))} />) }} detail={createDialog} />;
  return <DetailLayout title={batch.data?.title ?? t`QR labels`} back={{ label: t`All batches`, onClick: () => setBatchId("") }} state={inventoryQueryState(batch, "this label batch")} meta={[`${batchItems.length} labels`]}
    actions={{ primary: { label: t`Download all (ZIP)`, pending: downloadZip.isPending, pendingLabel: t`Preparing…`, disabled: !batchItems.length, disabledReason: t`Add a label to this batch first.`, onClick: () => downloadZip.mutate() },
      secondary: { label: t`New batch`, icon: "Plus", onClick: () => setBatchModalOpen(true) } }}
    main={<div className="grid gap-6">
        <ActionBox title={t`Add labels`}>
          <SegmentedControl label={t`Label type`} value={labelMode} options={[{ value: "item", label: t`Item` }, { value: "units", label: t`Units` }, { value: "reprint", label: t`Reprint a unit` }]} onChange={value => { setLabelMode(value); setProductId(""); setAssetId(""); }} />
          <Field label={t`Inventory item`}><select className="desk-input w-full" value={productId} disabled={!hasBatch || products.isLoading} onChange={(event) => selectProduct(event.target.value)}>
            <option value="">{t`Inventory item`}</option>
            {productOptions.filter(product => labelMode === "item" ? product.tracking_mode !== "individual" : product.tracking_mode === "individual").map((product) => (
              <option key={product.id} value={product.id}>
                {product.name} | {product.tracking_mode} | {product.available_quantity} available
              </option>
            ))}
          </select></Field>
          {selectedProduct ? <p className="mt-2 text-xs uppercase text-muted">{selectedProduct.tracking_mode}</p> : null}
          {selectedIsIndividual && !assetUnitsEnabled ? (
            <p className="mt-2 text-sm text-muted">
              {t`Unit QR generation needs the Asset units module.`}</p>
          ) : null}
          {selectedIsIndividual && assetUnitsEnabled ? (
            <div className="mt-2 grid gap-3">
              {labelMode === "units" ? <div className="grid gap-2 sm:grid-cols-[110px_1fr_auto]">
                <Field label={t`Unit count`}><input className="desk-input" inputMode="numeric" value={assetCount} onChange={(event) => setAssetCount(event.target.value)} /></Field>
                <Field label={t`Label prefix`}><input className="desk-input" value={assetPrefix} onChange={(event) => setAssetPrefix(event.target.value)} /></Field>
                <button className="desk-button" type="button" disabled={!canGenerateAssets || generateAssets.isPending} onClick={() => generateAssets.mutate()}>
                  {generateAssets.isPending ? <><BoxArt size={16} mono />{t`Generating…`}</> : t`Generate missing/new unit QRs`}
                </button>
              </div> : null}
              {labelMode === "reprint" ? <div className="grid gap-2 border-t border-line pt-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                <Field label={t`Existing unit to reprint`}><select className="desk-input w-full" value={assetId} disabled={!hasBatch || assets.isLoading} onChange={(event) => setAssetId(event.target.value)}>
                  <option value="">{t`Existing unit to reprint`}</option>
                  {assetOptions.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.asset_tag} | {asset.status} | {asset.qr_code_id ? t`QR #${asset.qr_code_id}` : t`no QR linked`}
                    </option>
                  ))}
                </select></Field>
                <button className="desk-button" type="button" disabled={!canReprintAsset || reprintAsset.isPending} onClick={() => reprintAsset.mutate()}>
                  {reprintAsset.isPending ? <><BoxArt size={16} mono />{t`Adding…`}</> : t`Reprint unit QR`}
                </button>
              </div> : null}
              {assets.isLoading ? <LogoLoader label={t`Loading units…`} size={48} className="min-h-16 py-3" /> : null}
              {assets.isError ? <ErrorText message={assets.error.message} /> : null}
              {!assets.isLoading && selectedProduct && !assetOptions.length ? <p className="text-sm text-muted">{t`No individual units yet.`}</p> : null}
            </div>
          ) : null}
          {labelMode === "item" ? (
            <button className="desk-button mt-2" type="button" disabled={!canAddItemQr || addProduct.isPending} onClick={() => addProduct.mutate()}>
              {addProduct.isPending ? <><BoxArt size={16} mono />{t`Adding…`}</> : t`Add/reprint item QR`}
            </button>
          ) : null}
          {addProduct.isError ? <ErrorText message={addProduct.error.message} /> : null}
          {reprintAsset.isError ? <ErrorText message={reprintAsset.error.message} /> : null}
          {generateAssets.isError ? <ErrorText message={generateAssets.error.message} /> : null}
        </ActionBox>

        <div className="rounded-md border border-line bg-surface p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="title-section">{t`Labels in this batch`}</h3>
              <p className="text-sm text-muted">{t`${batchItems.length} QR labels accumulated`}</p>
            </div>

          </div>
          {batch.isLoading ? <LogoLoader label={t`Loading batch…`} size={48} className="min-h-16 py-3" /> : null}
          {batch.isError ? <ErrorText message={batch.error.message} /> : null}
          {!batch.isLoading && !batchItems.length ? <EmptyState message={t`This batch is empty. Add an item or units to start.`} /> : null}
          {/* Fill by label size, not breakpoint: two labels across a phone, more on wide screens, never one giant QR. */}
          <div className="mt-4 grid grid-cols-[repeat(auto-fill,minmax(min(9rem,100%),1fr))] gap-3">
            {batchItems.map((item) => (
              <article key={item.id} className="rounded-md border border-line bg-bg p-3 text-center">
                <QrImage qrId={item.qr_code.id} label={item.label_text} />
                <p className="mt-2 text-sm font-semibold text-ink [overflow-wrap:anywhere]">{item.label_text}</p>
                <p className="text-xs text-muted">{item.target_type} #{item.target_id}</p>
              </article>
            ))}
          </div>
          {downloadZip.isError ? <ErrorText message={(downloadZip.error as Error).message} /> : null}
        </div>
        {labelPrintersOn && Number(batchId) ? <QrLabelPrinterSend makerspaceId={makerspace.id} batchId={Number(batchId)} hasItems={batchItems.length > 0} /> : null}
        {createDialog}
    </div>} />;
}

function ActionBox({ children, title }: { children: React.ReactNode; title: string }) {
  return <section className="rounded-md border border-line bg-surface p-3"><h3 className="title-section mb-2">{title}</h3>{children}</section>;
}

function ModalActions(props: { pending: boolean; disabled: boolean; submitLabel: string; onCancel: () => void; onSubmit: () => void }) {
  return (
    <div className="flex flex-wrap justify-end gap-2">
      <button className="desk-button-ghost" type="button" disabled={props.pending} onClick={props.onCancel}>{t`Cancel`}</button>
      <button className="desk-button-primary" type="button" disabled={props.pending || props.disabled} onClick={props.onSubmit}>
        {props.pending ? <><BoxArt size={16} mono />{t`Saving…`}</> : props.submitLabel}
      </button>
    </div>
  );
}
