import { t } from "@lingui/core/macro";
import { ListLayout, FlowLayout } from "../../../components/layouts";
import { Callout, ErrorText, Field, OverflowMenu } from "../../../components/ui";
import { inventoryQueryState } from "./inventoryPresentation";
import { useStockTransfer, labelForContainer } from "./useStockTransfer";
import { TransferTable } from "./StockTransferTable";
import { QuantityStepper } from "../QuantityStepper";
import type { Makerspace } from "./shared";
export type { Transfer } from "./useStockTransfer";
export function StockTransferPanel({ makerspace, makerspaces, isSuperadmin, canEditInventory = false }: {
 makerspace: Makerspace; makerspaces: Makerspace[]; isSuperadmin: boolean; canEditInventory?: boolean;
}) {
 const {
   canCreate, spaceOptions, sourceMakerspaceId, changeSource, destinationMakerspaceId,
   setDestinationMakerspaceId, sourceContainerId, setSourceContainerId, destinationContainerId, setDestinationContainerId,
   sourceContainers, destinationContainers, isCrossMakerspace, step, setStep,
   open, setOpen, reason, setReason, lineRows,
   updateLine, removeLine, addLine, products, create,
   validationError, submit, transfers, makerspaceNames, sourceContainerNames,
   destinationContainerNames,
 } = useStockTransfer({ makerspace, makerspaces, isSuperadmin, canEditInventory });
  return <ListLayout header={{ title: t`Transfers`, subtitle: t`Stock moved between boxes and spaces.`, primary: canCreate ? { label: t`New transfer`, onClick: () => { setStep("from"); setOpen(true); } } : undefined }}
    callout={!canCreate ? { size: "inline", tone: "warn", lead: t`Transfers are managed by inventory staff.`, body: t`This view is read-only.` } : undefined}
    filters={isSuperadmin && spaceOptions.length > 1 ? { views: <label className="relative flex h-11 min-w-0 items-center">
      <span aria-hidden="true" className="pointer-events-none absolute left-3 text-sm text-muted">{t`Makerspace:`}</span><span className="sr-only">{t`Show transfers for makerspace`}</span>
      <select className="desk-input h-11 w-full min-w-0 pl-28" value={sourceMakerspaceId} onChange={event => changeSource(Number(event.target.value))}>
        {spaceOptions.map(space => <option key={space.id} value={space.id}>{space.name}</option>)}</select></label> } : undefined}
    state={inventoryQueryState(transfers, "transfers")} isEmpty={!transfers.results.length}
    empty={{ message: t`No transfers yet. Move stock between boxes or spaces with New transfer.`, action: canCreate ? { label: t`New transfer`, onClick: () => setOpen(true) } : undefined }}
    body={{ kind: "rows", rows: <TransferTable transfers={transfers.results} makerspaceNames={makerspaceNames} sourceContainerNames={sourceContainerNames} destinationContainerNames={destinationContainerNames} /> }}
    pagination={{ page: transfers.page, pageSize: transfers.pageSize, count: transfers.count, onChange: transfers.setPage }}
    detail={canCreate ? <FlowLayout presentation="dialog" open={open} title={t`New transfer`} standalone={false} state={{ status: "ready" }} current={step}
      steps={[{ key: "from", label: t`From and to`, state: step === "from" ? "current" : "done" }, { key: "lines", label: t`What's moving`, state: step === "lines" ? "current" : "todo" }]} onCancel={() => setOpen(false)}
      leaveGuard={reason.trim() || lineRows.some(line => line.productId) ? "Leave this transfer? Your draft will stay here until you start another transfer." : undefined}
      footer={{ back: step === "lines" ? { label: t`Back`, onClick: () => setStep("from") } : undefined,
        next: step === "from" ? { label: t`Next`, onClick: () => setStep("lines") } : { label: t`Move stock`, pending: create.isPending, pendingLabel: t`Moving…`, onClick: submit } }}
      work={<div className="@container grid gap-4">{step === "from" ? <>
            <div className="grid gap-3 @xl:grid-cols-2">
              {isSuperadmin ? (
                <>
                  <Field label={t`Source makerspace`}>
                    <select className="desk-input w-full" value={sourceMakerspaceId} onChange={(event) => changeSource(Number(event.target.value))}>
                      {spaceOptions.map((space) => <option key={space.id} value={space.id}>{space.name}</option>)}
                    </select>
                  </Field>
                  <Field label={t`Destination makerspace`}>
                    <select className="desk-input w-full" value={destinationMakerspaceId} onChange={(event) => { setDestinationMakerspaceId(Number(event.target.value)); setDestinationContainerId(""); }}>
                      {spaceOptions.map((space) => <option key={space.id} value={space.id}>{space.name}</option>)}
                    </select>
                  </Field>
                </>
              ) : null}
              <Field label={t`Source container`}>
                <select className="desk-input w-full" value={sourceContainerId} disabled={isCrossMakerspace || sourceContainers.isLoading} onChange={(event) => setSourceContainerId(event.target.value)}>
                  <option value="">{t`Any source container`}</option>
                  {sourceContainers.data?.results?.map((box) => <option key={box.id} value={box.id}>{labelForContainer(box)}</option>)}
                </select>
                {isCrossMakerspace ? (
                  <p className="mt-1 text-xs text-muted">
                    {t`Source container is ignored for makerspace-to-makerspace transfers.`}</p>
                ) : null}
              </Field>
              <Field label={t`Destination container`}>
                <select className="desk-input w-full" value={destinationContainerId} disabled={destinationContainers.isLoading} onChange={(event) => setDestinationContainerId(event.target.value)}>
                  <option value="">{t`No destination container`}</option>
                  {destinationContainers.data?.results?.map((box) => <option key={box.id} value={box.id}>{labelForContainer(box)}</option>)}
                </select>
              </Field>
            </div>

        {(sourceContainers.error || destinationContainers.error) ? <ErrorText message={(sourceContainers.error || destinationContainers.error)?.message} /> : null}
      </> : <>

            <div className="mt-4">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
                <h3 className="title-section">{t`Transfer lines`}</h3>
                <button className="desk-button-ghost" type="button" onClick={addLine}>{t`Add line`}</button>
              </div>
              <div className="grid gap-2">
                {lineRows.map((line, index) => (
                  <div key={line.key} className="grid gap-2 @xl:grid-cols-[minmax(0,1fr)_auto_auto] @xl:items-end">
                    <Field label={t`Product for transfer line ${index + 1}`}><select className="desk-input" value={line.productId} disabled={products.isLoading} onChange={(event) => updateLine(line.key, { productId: event.target.value })}>
                      <option value="">{t`Product`}</option>
                      {products.data?.results?.map((product) => <option key={product.id} value={product.id}>{product.name} ({product.available_quantity} available)</option>)}
                    </select></Field>
                    <Field label={t`Quantity for transfer line ${index + 1}`}><QuantityStepper label="quantity" min={1} value={line.quantity} onValueChange={(value) => updateLine(line.key, { quantity: value })} /></Field>
                    <OverflowMenu label={t`Actions for line ${index + 1}`} actions={[{ label: t`Remove line`, onClick: () => removeLine(line.key) }]} />
                  </div>
                ))}
              </div>
            </div>

            <Field label={t`Reason`} className="mt-4">
              <input className="desk-input w-full" value={reason} placeholder={t`Why is this stock moving?`} onChange={(event) => setReason(event.target.value)} />
            </Field>
            {isCrossMakerspace ? <Callout size="panel" tone="warn" lead={`This moves stock to ${makerspaceNames.get(destinationMakerspaceId) ?? "the destination"}.`}
              body={t`A matching product is created there if needed and stays private until they publish it.`} /> : null}
            {isCrossMakerspace ? <details><summary className="desk-button-ghost">{t`Read the details`}</summary><p className="text-sm text-muted">{t`Only available stock can move. Individual asset-tracked products are not supported. The source container is ignored for transfers between makerspaces.`}</p></details> : null}

        <ErrorText message={validationError || create.error?.message || products.error?.message} />
      </>}</div>} /> : undefined} />;
}