import { t } from "@lingui/core/macro";
import { InventoryDetailNavigation } from "./InventoryDetailNavigation";
import type { Dispatch, SetStateAction } from "react";
import { useSearchParams } from "react-router-dom";
import { DetailLayout } from "../../../components/layouts";
import { ErrorText, SettingsActions, StatCard } from "../../../components/ui";
import { ImageUploader } from "../ImageUploader";
import { KitDefinitionEditor } from "../../inventory/KitChecklist";
import { ChainOfCustodyBlock } from "./LoanTimeline";
import { InventoryItemFields } from "./InventoryItemFields";
import { PriceOverrideCard } from "../pricing/PriceOverrideCard";
import { IndividualAssets, InventoryAvailability, QrHistory, QuantityAdjust } from "./InventoryPanelParts";
import { LendingHistory } from "./InventoryLendingHistory";
import { InventoryItemRelated } from "./InventoryItemRelated";
import { formFromProduct, type AdjustmentForm, type AdminProduct, type ItemForm } from "./InventoryPanelShared";
import type { Category, Makerspace } from "./shared";
import { capabilityOn } from "../../../lib/features";
import { ItemWaitlist } from "./ItemWaitlist";
import { ShowOnShelf } from "../shelf/ShowOnShelf";
export function InventoryItemDetail({ product, makerspace, canViewAudit, kitEnabled, form, setForm, categories, onClose, pending, error, onSave, onArchive,
  adjustForm, setAdjustForm, adjustPending, adjustError, onAdjust, invalidate }: {
  product: AdminProduct; makerspace: Makerspace; canViewAudit: boolean; kitEnabled: boolean; form: ItemForm; setForm: Dispatch<SetStateAction<ItemForm>>;
  categories: Category[]; onClose: () => void; pending: boolean; error?: string; onSave: () => void; onArchive: () => void;
  adjustForm: AdjustmentForm; setAdjustForm: Dispatch<SetStateAction<AdjustmentForm>>; adjustPending: boolean; adjustError?: string; onAdjust: () => void; invalidate: () => void;
}) {
  const [params] = useSearchParams();
  const allowed = ["details", "stock", "qr", ...(canViewAudit ? ["history", "custody"] : []), "related"];
  const active = allowed.includes(params.get("itemTab") ?? "") ? params.get("itemTab")! : "details";
  const href = (key: string) => { const next = new URLSearchParams(params); next.set("itemTab", key); return `?${next}`; };
  const original = { ...formFromProduct(product), ...(kitEnabled ? { kit_components: product.kit_components ?? [] } : {}) };
  const dirty = JSON.stringify(form) !== JSON.stringify(original);
  return <InventoryDetailNavigation><DetailLayout presentation="drawer" open onClose={onClose} drawerWidth={720} title={product.name}
    identity={product.image_url ? { kind: "image", src: product.image_url } : { kind: "icon", icon: "Circle", tone: "accent" }}
    status={<InventoryAvailability product={product} />} state={{ status: "ready" }}
    meta={[product.tracking_mode === "individual" ? t`Individual units` : t`Count-tracked`, form.is_public ? t`Public item` : t`Private item`]}
    actions={product.is_public ? { secondary: { label: t`View public page ↗`, href: `/m/${makerspace.slug}/items/${product.id}`, external: true } } : undefined}
    tabs={allowed.map(key => ({ key, label: ({ details: t`Details`, stock: t`Stock`, qr: t`QR & assets`, history: t`History`, custody: t`Custody`, related: t`Related` } as Record<string, string>)[key], href: href(key) }))} activeTab={active}
    main={<>
      {active === "details" ? <ShowOnShelf makerspaceId={makerspace.id} targetType="item" targetId={product.id} /> : null}
      {active === "details" ? <><InventoryItemFields form={form} setForm={setForm} categories={categories} error={error} makerspace={makerspace}>
        {kitEnabled ? <KitDefinitionEditor value={form.kit_components ?? []} onChange={value => setForm(current => ({ ...current, kit_components: value }))} /> : null}
        <ImageUploader endpoint={`/admin/inventory/${product.id}/image`} currentUrl={product.image_url} label={t`Item photo`} onChanged={invalidate} />
        <PriceOverrideCard makerspaceId={makerspace.id} targetType="inventory_product" targetId={product.id} />
      </InventoryItemFields>{dirty ? <SettingsActions onDiscard={() => setForm(original)} onSave={onSave} pending={pending} disabled={!form.name.trim()} /> : null}</> : null}
      {active === "stock" ? <div className="@container grid gap-6"><div className="grid grid-cols-2 gap-3 @xl:grid-cols-3">{[
        [t`Total`, product.total_quantity], [t`Available`, product.available_quantity], [t`Issued`, product.issued_quantity], [t`Damaged`, product.damaged_quantity], [t`Lost`, product.lost_quantity],
      ].map(([label, value]) => <StatCard key={label} label={String(label)} value={value} />)}</div>
        <QuantityAdjust product={product} form={adjustForm} setForm={setAdjustForm} pending={adjustPending} error={adjustError} onSubmit={onAdjust} />
        {product.tracking_mode === "individual" ? <IndividualAssets productId={product.id} makerspaceId={makerspace.id} refreshInventory={invalidate} /> : null}
        {capabilityOn(makerspace, "loans.waitlist") ? <ItemWaitlist makerspaceId={makerspace.id} productId={product.id} /> : null}</div> : null}
      {active === "qr" ? <><QrHistory defaultOpen title={t`Product QR history`} queryKey={["product-qr-history", product.id]} path={`/admin/inventory/${product.id}/qr-history`} />{product.tracking_mode === "individual" ? <IndividualAssets productId={product.id} makerspaceId={makerspace.id} refreshInventory={invalidate} /> : null}</> : null}
      {active === "history" && canViewAudit ? <LendingHistory productId={product.id} /> : null}
      {active === "custody" && canViewAudit ? <ChainOfCustodyBlock productId={product.id} /> : null}
      {active === "related" ? <InventoryItemRelated product={product} makerspaceId={makerspace.id} /> : null}
      <ErrorText message={error} />
    </>}
    danger={!product.is_archived ? [{ title: t`Archive item`, consequence: t`Hides this item from active inventory and the public catalogue. You can undo this change.`, action: { label: t`Archive`, onClick: onArchive, confirm: { title: t`Archive ${product.name}?`, message: t`It leaves the catalogue and can no longer be requested. You can bring it back from the Archived tab.` } } }] : undefined} /></InventoryDetailNavigation>;
}
