import { ListLayout } from "../../../components/layouts";
import { ConfirmDialog, DangerZone, ErrorText, ScanWorkbench, StatusPill } from "../../../components/ui";
import { ScannerMoveAssetForm, ScannerRebindForm } from "./ScannerPanelForms";
import { useStaffScanner } from "./useStaffScanner";
import type { Makerspace } from "./shared";
export function ScannerPanel(props: { makerspace: Makerspace; isSuperadmin: boolean; makerspaces: Makerspace[] }) {
  const {
    doResolve, resolveFromScan, resolve, recent, scanNote, resolveError,
    revokeError, loadContents, successNote, resolved, target, actions,
    showRebind, setShowRebind, canRebind, canMoveAsset, setShowMove, showMove,
    setConfirmRevoke, confirmRevoke, revoke, rebindMakerspace, rebindMakerspaceId, productRows,
    products, selectedProductId, setSelectedProductId, newName, setNewName, rebind,
    productError, rebindError, destinationMakerspaces, destMakerspaceId, setDestMakerspaceId, destProductId,
    setDestProductId, destinationProductRows, destinationProducts, moveTag, setMoveTag, moveAsset,
    destinationProductError, moveError, contents,
} = useStaffScanner(props);
  return <ListLayout header={{ title: "Scanner", subtitle: "Scan a label to find a box, product or asset and choose the next step." }} state={{ status: "ready" }}
    empty={{ message: "Scan a QR code or find an item to get started." }}
    body={{ kind: "rows", rows: <ScanWorkbench searchLabel="QR payload" onFind={doResolve} onScan={resolveFromScan} findPending={resolve.isPending}
      recent={recent} controls={<>
        {scanNote && resolve.isPending ? <p role="status" className="text-sm text-muted">{scanNote}</p> : null}
        <ErrorText message={resolveError || loadContents.error?.message} />
        {successNote ? <p role="status" className="text-sm text-accent-ink">{successNote}</p> : null}
      {resolved && target ? (
        <div className="mt-4 rounded-md border border-line bg-surface p-3">
          <h3 className="title-section [overflow-wrap:anywhere]">
            {target.type === "box" ? `Box: ${target.label} (${target.code})`
              : target.type === "product" ? `Product: ${target.name}`
              : `Asset: ${target.asset_tag} - ${target.product} (${target.status})`}
          </h3>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">QR #{resolved.qr.id}<StatusPill label={resolved.qr.status} /></p>
          <div className="desk-actions mt-3 flex flex-wrap gap-2 text-sm">
            {actions.includes("contents") && target.type === "box" ? (
              <button className="desk-button-ghost" type="button" disabled={loadContents.isPending} onClick={() => loadContents.mutate(target.id)}>View contents</button>
            ) : null}
            {canRebind ? (
              <button className="desk-button-ghost" type="button" onClick={() => setShowRebind((open) => !open)}>
                Rename & rebind
              </button>
            ) : null}
            {canMoveAsset ? (
              <button className="desk-button-ghost" type="button" onClick={() => setShowMove((open) => !open)}>
                Move to makerspace
              </button>
            ) : null}
          </div>
          {showRebind ? (
            <ScannerRebindForm
              makerspaceLabel={rebindMakerspace?.name ?? `Makerspace #${rebindMakerspaceId}`}
              productRows={productRows}
              productsLoading={products.isLoading}
              selectedProductId={selectedProductId}
              onSelectProduct={setSelectedProductId}
              newName={newName}
              onNewNameChange={setNewName}
              pending={rebind.isPending}
              onSubmit={() => rebind.mutate()}
              onCancel={() => setShowRebind(false)}
              productError={productError}
              rebindError={rebindError}
            />
          ) : null}
          {canMoveAsset && showMove ? (
            <ScannerMoveAssetForm
              destinationMakerspaces={destinationMakerspaces}
              destMakerspaceId={destMakerspaceId}
              onDestMakerspaceChange={(value) => {
                setDestMakerspaceId(value);
                setDestProductId("");
              }}
              destProductId={destProductId}
              onDestProductChange={setDestProductId}
              destinationProductRows={destinationProductRows}
              destinationProductsLoading={destinationProducts.isLoading}
              moveTag={moveTag}
              onMoveTagChange={setMoveTag}
              pending={moveAsset.isPending}
              onSubmit={() => moveAsset.mutate()}
              onCancel={() => setShowMove(false)}
              destinationProductError={destinationProductError}
              moveError={moveError}
            />
          ) : null}
          {actions.some((action) => ["checkout", "return", "direct_handout"].includes(action)) ? (
            <p className="mt-2 text-xs text-muted">
              This item supports {actions.filter((a) => ["checkout", "return", "direct_handout"].includes(a)).join(" / ")} -
              use the Direct handout tab (or the public self-checkout page) which collect the borrower identity.
            </p>
          ) : null}
          {revokeError ? <p className="mt-2 text-sm text-danger">{revokeError}</p> : null}
          {contents ? (
            <div className="mt-3 rounded-md border border-line bg-bg p-2 text-xs text-muted [overflow-wrap:anywhere]">
              <h4 className="title-section">Contents</h4>
              {contents.products.map((product) => <p key={`p-${product.id}`}>{product.name} - {product.available_quantity} available</p>)}
              {contents.assets.map((asset) => <p key={`a-${asset.id}`}>{asset.asset_tag} ({asset.status})</p>)}
              {!contents.products.length && !contents.assets.length ? <p>Empty.</p> : null}
            </div>
          ) : null}
          {actions.includes("revoke") ? <DangerZone title="Revoke this QR code" consequence="This label will stop resolving for future scans." action={{ label: "Revoke QR", pending: revoke.isPending, pendingLabel: "Revoking…", onClick: () => setConfirmRevoke(true) }} /> : null}
        </div>
      ) : null}

      </>} /> }}
    detail={<ConfirmDialog open={confirmRevoke} title="Revoke this QR code?" message="This label will stop resolving for future scans. Print a new label to replace it." confirmLabel="Revoke QR" tone="danger" pending={revoke.isPending} onCancel={() => setConfirmRevoke(false)} onConfirm={() => { if (resolved) revoke.mutate(resolved.qr.id); }} />} />;
}
