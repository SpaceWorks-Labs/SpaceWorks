import { InventoryDetailNavigation } from "./InventoryDetailNavigation";
import type { Dispatch, SetStateAction } from "react";
import { useSearchParams } from "react-router-dom";
import { DetailLayout } from "../../../components/layouts";
import { ErrorText, SettingsActions, StatCard } from "../../../components/ui";
import { ImageUploader } from "../ImageUploader";
import { KitDefinitionEditor } from "../../inventory/KitChecklist";
import { ChainOfCustodyBlock } from "./LoanTimeline";
import { InventoryItemFields } from "./InventoryItemFields";
import { IndividualAssets, InventoryAvailability, LendingHistory, QrHistory, QuantityAdjust } from "./InventoryPanelParts";
import { formFromProduct, type AdjustmentForm, type AdminProduct, type ItemForm } from "./InventoryPanelShared";
import type { Category, Makerspace } from "./shared";
export function InventoryItemDetail({ product, makerspace, canViewAudit, kitEnabled, form, setForm, categories, onClose, pending, error, onSave, onArchive,
  adjustForm, setAdjustForm, adjustPending, adjustError, onAdjust, invalidate }: {
  product: AdminProduct; makerspace: Makerspace; canViewAudit: boolean; kitEnabled: boolean; form: ItemForm; setForm: Dispatch<SetStateAction<ItemForm>>;
  categories: Category[]; onClose: () => void; pending: boolean; error?: string; onSave: () => void; onArchive: () => void;
  adjustForm: AdjustmentForm; setAdjustForm: Dispatch<SetStateAction<AdjustmentForm>>; adjustPending: boolean; adjustError?: string; onAdjust: () => void; invalidate: () => void;
}) {
  const [params] = useSearchParams();
  const allowed = ["details", "stock", "qr", ...(canViewAudit ? ["history", "custody"] : [])];
  const active = allowed.includes(params.get("itemTab") ?? "") ? params.get("itemTab")! : "details";
  const href = (key: string) => { const next = new URLSearchParams(params); next.set("itemTab", key); return `?${next}`; };
  const original = { ...formFromProduct(product), ...(kitEnabled ? { kit_components: product.kit_components ?? [] } : {}) };
  const dirty = JSON.stringify(form) !== JSON.stringify(original);
  return <InventoryDetailNavigation><DetailLayout presentation="drawer" open onClose={onClose} drawerWidth={720} title={product.name}
    identity={product.image_url ? { kind: "image", src: product.image_url } : { kind: "icon", icon: "Circle", tone: "accent" }}
    status={<InventoryAvailability product={product} />} state={{ status: "ready" }}
    meta={[product.tracking_mode === "individual" ? "Individual units" : "Count-tracked", form.is_public ? "Public item" : "Private item"]}
    actions={product.is_public ? { secondary: { label: "View public page ↗", href: `/m/${makerspace.slug}/items/${product.id}`, external: true } } : undefined}
    tabs={allowed.map(key => ({ key, label: ({ details: "Details", stock: "Stock", qr: "QR & assets", history: "History", custody: "Custody" } as Record<string, string>)[key], href: href(key) }))} activeTab={active}
    main={<>
      {active === "details" ? <><InventoryItemFields form={form} setForm={setForm} categories={categories} error={error}>
        {kitEnabled ? <KitDefinitionEditor value={form.kit_components ?? []} onChange={value => setForm(current => ({ ...current, kit_components: value }))} /> : null}
        <ImageUploader endpoint={`/admin/inventory/${product.id}/image`} currentUrl={product.image_url} label="Item photo" onChanged={invalidate} />
      </InventoryItemFields>{dirty ? <SettingsActions onDiscard={() => setForm(original)} onSave={onSave} pending={pending} disabled={!form.name.trim()} /> : null}</> : null}
      {active === "stock" ? <div className="@container grid gap-6"><div className="grid grid-cols-2 gap-3 @xl:grid-cols-3">{[
        ["Total", product.total_quantity], ["Available", product.available_quantity], ["Issued", product.issued_quantity], ["Damaged", product.damaged_quantity], ["Lost", product.lost_quantity],
      ].map(([label, value]) => <StatCard key={label} label={String(label)} value={value} />)}</div>
        <QuantityAdjust product={product} form={adjustForm} setForm={setAdjustForm} pending={adjustPending} error={adjustError} onSubmit={onAdjust} />
        {product.tracking_mode === "individual" ? <IndividualAssets productId={product.id} makerspaceId={makerspace.id} refreshInventory={invalidate} /> : null}</div> : null}
      {active === "qr" ? <><QrHistory defaultOpen title="Product QR history" queryKey={["product-qr-history", product.id]} path={`/admin/inventory/${product.id}/qr-history`} />{product.tracking_mode === "individual" ? <IndividualAssets productId={product.id} makerspaceId={makerspace.id} refreshInventory={invalidate} /> : null}</> : null}
      {active === "history" && canViewAudit ? <LendingHistory productId={product.id} /> : null}
      {active === "custody" && canViewAudit ? <ChainOfCustodyBlock productId={product.id} /> : null}
      <ErrorText message={error} />
    </>}
    danger={!product.is_archived ? [{ title: "Archive item", consequence: "Hides this item from active inventory and the public catalogue. You can undo this change.", action: { label: "Archive", onClick: onArchive, confirm: { title: `Archive ${product.name}?`, message: "It leaves the catalogue and can no longer be requested. You can bring it back from the Archived tab." } } }] : undefined} /></InventoryDetailNavigation>;
}
