import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { Field, SegmentedControl, SettingsRow, StatusPill } from "../../../components/ui";
import { ProductMasterFields } from "./ProductMasterFields";
import type { Category } from "./shared";
import type { ItemForm } from "./InventoryPanelShared";
import { publicPreviewAvailability } from "./InventoryPublicPreview";
import { InventoryLendingFlags, type LendingFlagSpace } from "./InventoryLendingFlags";
export function InventoryItemFields({ form, setForm, categories, includeQuantities = false, error, children, makerspace }: {
 form: ItemForm; setForm: (updater: (current: ItemForm) => ItemForm) => void; categories: Category[];
 includeQuantities?: boolean; error?: string; children?: ReactNode; makerspace?: LendingFlagSpace;
}) {
 const availability = publicPreviewAvailability(form);
 const preview = !form.is_public ? "Not in the public catalogue" : availability === null ? "Availability hidden" : availability.mode === "exact_count" ? `${availability.count} available` : availability.label ?? "Available";
 return <div className="divide-y divide-line">
   <SettingsRow label={t`Name and description`} helper="Help members recognise this item."><div className="grid gap-4">
     <Field label={t`Name`}><input className="desk-input" required placeholder={t`e.g. Soldering iron`} value={form.name} onChange={e => setForm(c => ({ ...c, name: e.target.value }))} /></Field>
     <Field label={t`Description`}><textarea className="desk-input min-h-24" placeholder={t`Optional notes`} value={form.description} onChange={e => setForm(c => ({ ...c, description: e.target.value }))} /></Field>
   </div></SettingsRow>
   <SettingsRow label={t`Category and tracking`}><div className="grid gap-4">
     <Field label={t`Category`}><select className="desk-input" value={form.category} onChange={e => setForm(c => ({ ...c, category: e.target.value }))}><option value="">{t`Uncategorized`}</option>{categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}</select></Field>
     <Field label={t`Tracking mode`}><select className="desk-input" value={form.tracking_mode} onChange={e => setForm(c => ({ ...c, tracking_mode: e.target.value, ...(e.target.value !== "quantity" && c.is_consumable ? { is_consumable: false } : {}) }))}><option value="quantity">{t`Quantity`}</option><option value="individual">{t`Individual`}</option></select></Field>
   </div></SettingsRow>
   <SettingsRow label={t`Storage and ordering`} helper="Storage locations stay private to staff."><div className="grid gap-4">
     <Field label={t`Storage location`}><input className="desk-input" placeholder={t`e.g. Shelf B3`} value={form.storage_location} onChange={e => setForm(c => ({ ...c, storage_location: e.target.value }))} /></Field>
     <ProductMasterFields form={form} setForm={setForm} />
   </div></SettingsRow>
   <InventoryLendingFlags form={form} setForm={setForm} makerspace={makerspace} />
   <SettingsRow label={t`Borrowing terms`}><Field label={t`Public borrowing terms`}><textarea className="desk-input min-h-24" maxLength={2000} placeholder={t`For example: return clean; bring required accessories.`} value={form.borrowing_terms} onChange={e => setForm(c => ({ ...c, borrowing_terms: e.target.value }))} /></Field></SettingsRow>
   {includeQuantities ? <SettingsRow label={t`Starting stock`}><div className="grid gap-4">
     <Field label={t`Total quantity`}><input className="desk-input" type="number" min="0" value={form.total_quantity} onChange={e => setForm(c => ({ ...c, total_quantity: e.target.value }))} /></Field>
     <Field label={t`Available quantity`}><input className="desk-input" type="number" min="0" value={form.available_quantity} onChange={e => setForm(c => ({ ...c, available_quantity: e.target.value }))} /></Field>
   </div></SettingsRow> : null}
   <SettingsRow label={t`Public visibility`} helper="Exact counts appear only when Show count is enabled."><div className="grid gap-4">
     <label className="inline-flex min-h-11 items-center gap-2"><input type="checkbox" checked={form.is_public} onChange={e => setForm(c => ({ ...c, is_public: e.target.checked }))} />{t`Public`}</label>
     <SegmentedControl label={t`Public visibility`} value={form.public_availability_mode} options={[{ value: "exact_count", label: t`Exact count` }, { value: "status_only", label: t`Status only` }, { value: "hidden", label: t`Hidden` }]} onChange={value => setForm(c => ({ ...c, public_availability_mode: value }))} />
     <label className="inline-flex min-h-11 items-center gap-2"><input type="checkbox" checked={form.show_public_count} onChange={e => setForm(c => ({ ...c, show_public_count: e.target.checked }))} />{t`Show count`}</label>
     <label className="inline-flex min-h-11 items-center gap-2"><input type="checkbox" checked={form.public_self_checkout_enabled} onChange={e => setForm(c => ({ ...c, public_self_checkout_enabled: e.target.checked }))} />{t`Self checkout`}</label>
     <StatusPill label={preview} />
   </div></SettingsRow>
   <SettingsRow label={t`Kit components and photo`}><div className="grid gap-4">
     {includeQuantities ? <p className="text-sm text-muted">{t`Save this item to add a photo. It will open for editing after it's created.`}</p> : null}{children}
   </div></SettingsRow>
   {error ? <p role="alert" className="pt-4 text-sm text-danger">{error}</p> : null}
 </div>;
}
