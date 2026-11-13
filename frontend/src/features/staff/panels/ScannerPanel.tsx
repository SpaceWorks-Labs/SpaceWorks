import { t } from "@lingui/core/macro";
import { ListLayout } from "../../../components/layouts";
import { ConfirmDialog, DangerZone, ErrorText, ScanWorkbench, StatusPill } from "../../../components/ui";
import { ScannerMoveAssetForm, ScannerRebindForm } from "./ScannerPanelForms";
import { ScannerUnknownCode } from "./ScannerUnknownCode";
import { useStaffScanner } from "./useStaffScanner";
import type { Makerspace } from "./shared";
import { assetStatusLabel } from "./InventoryPanelShared";
import { useGuestPassScanIntercept } from "../../guestPasses/staff/useGuestPassScanIntercept";

const HANDOUT_ACTIONS = ["checkout", "return", "direct_handout"];
const handoutActionLabel = (action: string) =>
  action === "checkout" ? t`check out` : action === "return" ? t`return` : t`direct handout`;
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
    unknownValue, setUnknownValue, canLinkExternal, canCreateExternal, onExternalLinked,
} = useStaffScanner(props);
  // Decision 223: a guest-pass QR is checked as a pass, not resolved as an inventory label.
  const guestPass = useGuestPassScanIntercept(props.makerspace);
  return <ListLayout header={{ title: t`Scanner`, subtitle: t`Scan a label to find a box, product or asset and choose the next step.` }} state={{ status: "ready" }}
    empty={{ message: t`Scan a QR code or find an item to get started.` }}
    body={{ kind: "rows", rows: <ScanWorkbench searchLabel="QR payload" onFind={(value) => { if (!guestPass.intercept(value)) doResolve(value); }} onScan={(value) => { if (!guestPass.intercept(value)) resolveFromScan(value); }} findPending={resolve.isPending}
      recent={recent} controls={<>
        {guestPass.panel}
        {scanNote && resolve.isPending ? <p role="status" className="text-sm text-muted">{scanNote}</p> : null}
        <ErrorText message={resolveError || loadContents.error?.message} />
        {successNote ? <p role="status" className="text-sm text-accent-ink">{successNote}</p> : null}
        {unknownValue && canLinkExternal && !resolved ? <ScannerUnknownCode key={unknownValue} makerspace={props.makerspace} value={unknownValue}
          canCreate={canCreateExternal} onLinked={onExternalLinked} onCancel={() => setUnknownValue(null)} /> : null}
      {resolved && target ? (
        <div className="mt-4 rounded-md border border-line bg-surface p-3">
          <h3 className="title-section [overflow-wrap:anywhere]">
            {target.type === "box" ? t`Box: ${target.label} (${target.code})`
              : target.type === "product" ? t`Product: ${target.name}`
              : t`Asset: ${target.asset_tag} - ${target.product} (${target.status})`}
          </h3>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">{t`QR #${resolved.qr.id}`}<StatusPill label={resolved.qr.status} />{resolved.qr.source === "external" ? <StatusPill label={t`External label`} /> : null}</p>
          <div className="desk-actions mt-3 flex flex-wrap gap-2 text-sm">
            {actions.includes("contents") && target.type === "box" ? (
              <button className="desk-button-ghost" type="button" disabled={loadContents.isPending} onClick={() => loadContents.mutate(target.id)}>{t`View contents`}</button>
            ) : null}
            {canRebind ? (
              <button className="desk-button-ghost" type="button" onClick={() => setShowRebind((open) => !open)}>
                {t`Rename & rebind`}</button>
            ) : null}
            {canMoveAsset ? (
              <button className="desk-button-ghost" type="button" onClick={() => setShowMove((open) => !open)}>
                {t`Move to makerspace`}</button>
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
          {actions.some((action) => HANDOUT_ACTIONS.includes(action)) ? (
            <p className="mt-2 text-xs text-muted">
              {t`This item supports ${actions.filter((a) => HANDOUT_ACTIONS.includes(a)).map(handoutActionLabel).join(" / ")}. Use the Direct handout tab (or the public self-checkout page), which collects the borrower identity.`}</p>
          ) : null}
          {revokeError ? <p className="mt-2 text-sm text-danger">{revokeError}</p> : null}
          {contents ? (
            <div className="mt-3 rounded-md border border-line bg-bg p-2 text-xs text-muted [overflow-wrap:anywhere]">
              <h4 className="title-section">{t`Contents`}</h4>
              {contents.products.map((product) => <p key={`p-${product.id}`}>{t`${product.name}: ${product.available_quantity} available`}</p>)}
              {contents.assets.map((asset) => <p key={`a-${asset.id}`}>{t`${asset.asset_tag} (${assetStatusLabel(asset.status)})`}</p>)}
              {!contents.products.length && !contents.assets.length ? <p>{t`Empty.`}</p> : null}
            </div>
          ) : null}
          {actions.includes("revoke") ? <DangerZone title={t`Revoke this QR code`} consequence={t`This label will stop resolving for future scans.`} action={{ label: t`Revoke QR`, pending: revoke.isPending, pendingLabel: t`Revoking…`, onClick: () => setConfirmRevoke(true) }} /> : null}
        </div>
      ) : null}

      </>} /> }}
    detail={<ConfirmDialog open={confirmRevoke} title={t`Revoke this QR code?`} message={t`This label will stop resolving for future scans. Print a new label to replace it.`} confirmLabel={t`Revoke QR`} tone="danger" pending={revoke.isPending} onCancel={() => setConfirmRevoke(false)} onConfirm={() => { if (resolved) revoke.mutate(resolved.qr.id); }} />} />;
}
