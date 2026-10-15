import { ListLayout, FlowLayout } from "../../../components/layouts";
import { Callout, ErrorText, Field, OverflowMenu } from "../../../components/ui";
import { inventoryQueryState } from "./inventoryPresentation";
import { useStockTransfer, labelForContainer } from "./useStockTransfer";
import { TransferTable } from "./StockTransferTable";
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
  return <ListLayout header={{ title: "Transfers", subtitle: "Stock moved between boxes and spaces.", primary: canCreate ? { label: "New transfer", onClick: () => { setStep("from"); setOpen(true); } } : undefined }}
    callout={!canCreate ? { size: "inline", tone: "warn", lead: "Transfers are managed by inventory staff.", body: "This view is read-only." } : undefined}
    filters={isSuperadmin && spaceOptions.length > 1 ? { views: <label className="relative flex h-11 min-w-0 items-center">
      <span aria-hidden="true" className="pointer-events-none absolute left-3 text-sm text-muted">Makerspace:</span><span className="sr-only">Show transfers for makerspace</span>
      <select className="desk-input h-11 w-full min-w-0 pl-28" value={sourceMakerspaceId} onChange={event => changeSource(Number(event.target.value))}>
        {spaceOptions.map(space => <option key={space.id} value={space.id}>{space.name}</option>)}</select></label> } : undefined}
    state={inventoryQueryState(transfers, "transfers")} isEmpty={!transfers.results.length}
    empty={{ message: "No transfers yet. Move stock between boxes or spaces with New transfer.", action: canCreate ? { label: "New transfer", onClick: () => setOpen(true) } : undefined }}
    body={{ kind: "rows", rows: <TransferTable transfers={transfers.results} makerspaceNames={makerspaceNames} sourceContainerNames={sourceContainerNames} destinationContainerNames={destinationContainerNames} /> }}
    pagination={{ page: transfers.page, pageSize: transfers.pageSize, count: transfers.count, onChange: transfers.setPage }}
    detail={canCreate ? <FlowLayout presentation="dialog" open={open} title="New transfer" standalone={false} state={{ status: "ready" }} current={step}
      steps={[{ key: "from", label: "From and to", state: step === "from" ? "current" : "done" }, { key: "lines", label: "What's moving", state: step === "lines" ? "current" : "todo" }]} onCancel={() => setOpen(false)}
      leaveGuard={reason.trim() || lineRows.some(line => line.productId) ? "Leave this transfer? Your draft will stay here until you start another transfer." : undefined}
      footer={{ back: step === "lines" ? { label: "Back", onClick: () => setStep("from") } : undefined,
        next: step === "from" ? { label: "Next", onClick: () => setStep("lines") } : { label: "Move stock", pending: create.isPending, pendingLabel: "Moving…", onClick: submit } }}
      work={<div className="grid gap-4">{step === "from" ? <>
            <div className="grid gap-3 lg:grid-cols-2">
              {isSuperadmin ? (
                <>
                  <Field label="Source makerspace">
                    <select className="desk-input w-full" value={sourceMakerspaceId} onChange={(event) => changeSource(Number(event.target.value))}>
                      {spaceOptions.map((space) => <option key={space.id} value={space.id}>{space.name}</option>)}
                    </select>
                  </Field>
                  <Field label="Destination makerspace">
                    <select className="desk-input w-full" value={destinationMakerspaceId} onChange={(event) => { setDestinationMakerspaceId(Number(event.target.value)); setDestinationContainerId(""); }}>
                      {spaceOptions.map((space) => <option key={space.id} value={space.id}>{space.name}</option>)}
                    </select>
                  </Field>
                </>
              ) : null}
              <Field label="Source container">
                <select className="desk-input w-full" value={sourceContainerId} disabled={isCrossMakerspace || sourceContainers.isLoading} onChange={(event) => setSourceContainerId(event.target.value)}>
                  <option value="">Any source container</option>
                  {sourceContainers.data?.results?.map((box) => <option key={box.id} value={box.id}>{labelForContainer(box)}</option>)}
                </select>
                {isCrossMakerspace ? (
                  <p className="mt-1 text-xs text-muted">
                    Source container is ignored for makerspace-to-makerspace transfers.
                  </p>
                ) : null}
              </Field>
              <Field label="Destination container">
                <select className="desk-input w-full" value={destinationContainerId} disabled={destinationContainers.isLoading} onChange={(event) => setDestinationContainerId(event.target.value)}>
                  <option value="">No destination container</option>
                  {destinationContainers.data?.results?.map((box) => <option key={box.id} value={box.id}>{labelForContainer(box)}</option>)}
                </select>
              </Field>
            </div>

        {(sourceContainers.error || destinationContainers.error) ? <ErrorText message={(sourceContainers.error || destinationContainers.error)?.message} /> : null}
      </> : <>

            <div className="mt-4">
              <div className="mb-2 flex items-center justify-between gap-3">
                <h3 className="title-section">Transfer lines</h3>
                <button className="desk-button-ghost" type="button" onClick={addLine}>Add line</button>
              </div>
              <div className="grid gap-2">
                {lineRows.map((line, index) => (
                  <div key={line.key} className="grid gap-2 md:grid-cols-[1fr_120px_auto]">
                    <Field label={`Product for transfer line ${index + 1}`}><select className="desk-input" value={line.productId} disabled={products.isLoading} onChange={(event) => updateLine(line.key, { productId: event.target.value })}>
                      <option value="">Product</option>
                      {products.data?.results?.map((product) => <option key={product.id} value={product.id}>{product.name} ({product.available_quantity} available)</option>)}
                    </select></Field>
                    <Field label={`Quantity for transfer line ${index + 1}`}><input className="desk-input" min={1} inputMode="numeric" type="number" value={line.quantity} onChange={(event) => updateLine(line.key, { quantity: event.target.value })} /></Field>
                    <OverflowMenu label={`Actions for line ${index + 1}`} actions={[{ label: "Remove line", onClick: () => removeLine(line.key) }]} />
                  </div>
                ))}
              </div>
            </div>

            <Field label="Reason" className="mt-4">
              <input className="desk-input w-full" value={reason} placeholder="Why is this stock moving?" onChange={(event) => setReason(event.target.value)} />
            </Field>
            {isCrossMakerspace ? <Callout size="panel" tone="warn" lead={`This moves stock to ${makerspaceNames.get(destinationMakerspaceId) ?? "the destination"}.`}
              body="A matching product is created there if needed and stays private until they publish it." /> : null}
            {isCrossMakerspace ? <details><summary className="desk-button-ghost">Read the details</summary><p className="text-sm text-muted">Only available stock can move. Individual asset-tracked products are not supported. The source container is ignored for transfers between makerspaces.</p></details> : null}

        <ErrorText message={validationError || create.error?.message || products.error?.message} />
      </>}</div>} /> : undefined} />;
}