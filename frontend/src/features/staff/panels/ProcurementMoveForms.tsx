import { t } from "@lingui/core/macro";
import { Field, SegmentedControl } from "../../../components/ui";
import type { Product } from "./shared";

type PrinterOption = { id: number; name: string };

export type ContainerOption = { id: number; label: string };
export type HardwareMode = "create" | "topup";
export type PrintingTarget = "spool" | "printer";

export type HardwareForm = {
  mode: HardwareMode;
  quantity: string;
  productId: string;
  name: string;
  description: string;
  category: string;
  box: string;
  trackingMode: "quantity" | "individual";
  isPublic: boolean;
  publicAvailabilityMode: "exact_count" | "status_only" | "hidden";
  showPublicCount: boolean;
  publicSelfCheckoutEnabled: boolean;
};

export type PrintingForm = {
  target: PrintingTarget;
  printerId: string;
  material: string;
  color: string;
  brand: string;
  initialWeight: string;
  remainingWeight: string;
  printerName: string;
  printerModel: string;
  printerStatus: "active" | "maintenance" | "offline";
};

export function HardwareMoveForm({ form, setForm, products, categories, containers }: {
  form: HardwareForm;
  setForm: (form: HardwareForm) => void;
  products: Product[];
  categories: { id: number; name: string }[];
  containers: ContainerOption[];
}) {
  return (
    <div className="grid gap-3">
      <SegmentedControl label={t`Inventory destination`} value={form.mode} options={[{ value: "create", label: t`Create item` }, { value: "topup", label: t`Top up` }]} onChange={mode => setForm({ ...form, mode: mode as HardwareMode })} />
      <Field label={t`Quantity`}><input className="desk-input" type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></Field>
      {form.mode === "topup" ? (
        <Field label={t`Existing product`}>
          <select className="desk-input" value={form.productId} onChange={(e) => setForm({ ...form, productId: e.target.value })}>
            <option value="">{t`Select product`}</option>
            {products.map((product) => <option key={product.id} value={product.id}>{product.name} ({product.available_quantity} available)</option>)}
          </select>
        </Field>
      ) : (
        <>
          <div className="grid gap-2 sm:grid-cols-2">
            <Field label={t`Name`}><input className="desk-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label={t`Tracking mode`}><select className="desk-input" value={form.trackingMode} onChange={(e) => setForm({ ...form, trackingMode: e.target.value as HardwareForm["trackingMode"] })}><option value="quantity">{t`Quantity`}</option><option value="individual">{t`Individual`}</option></select></Field>
          </div>
          <Field label={t`Description`}><textarea className="desk-input h-20" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <div className="grid gap-2 sm:grid-cols-2">
            <Field label={t`Category`}><select className="desk-input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}><option value="">{t`Uncategorized`}</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></Field>
            <Field label={t`Container`}><select className="desk-input" value={form.box} onChange={(e) => setForm({ ...form, box: e.target.value })}><option value="">{t`No container`}</option>{containers.map((container) => <option key={container.id} value={container.id}>{container.label}</option>)}</select></Field>
          </div>
          <div className="flex flex-wrap gap-x-6">
            <Check label={t`Public`} checked={form.isPublic} onChange={(value) => setForm({ ...form, isPublic: value })} />
            <Check label={t`Show count`} checked={form.showPublicCount} onChange={(value) => setForm({ ...form, showPublicCount: value })} />
            <Check label={t`Self checkout`} checked={form.publicSelfCheckoutEnabled} onChange={(value) => setForm({ ...form, publicSelfCheckoutEnabled: value })} />
          </div>
          <div className="grid gap-2">
            <Field label={t`Visibility`}><select className="desk-input" value={form.publicAvailabilityMode} onChange={(e) => setForm({ ...form, publicAvailabilityMode: e.target.value as HardwareForm["publicAvailabilityMode"] })}><option value="status_only">{t`Status only`}</option><option value="exact_count">{t`Exact count`}</option><option value="hidden">{t`Hidden`}</option></select></Field>
          </div>
        </>
      )}
    </div>
  );
}

export function PrintingMoveForm({ form, setForm, printers }: { form: PrintingForm; setForm: (form: PrintingForm) => void; printers: PrinterOption[] }) {
  return (
    <div className="grid gap-3">
      <SegmentedControl label={t`Printing destination`} value={form.target} options={[{ value: "spool", label: t`Spool` }, { value: "printer", label: t`Printer` }]} onChange={target => setForm({ ...form, target: target as PrintingTarget })} />
      {form.target === "spool" ? (
        <>
          <Field label={t`Printer`}><select className="desk-input" value={form.printerId} onChange={(e) => setForm({ ...form, printerId: e.target.value })}><option value="">{t`Unassigned printer`}</option>{printers.map((printer) => <option key={printer.id} value={printer.id}>{printer.name}</option>)}</select></Field>
          <div className="grid gap-2 sm:grid-cols-2"><Field label={t`Material`}><input className="desk-input" value={form.material} onChange={(e) => setForm({ ...form, material: e.target.value })} /></Field><Field label={t`Brand`}><input className="desk-input" value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} /></Field></div>
          <Field label={t`Color`}><input className="desk-input" value={form.color} onChange={(event) => setForm({ ...form, color: event.target.value })} /></Field>
          <div className="grid gap-2 sm:grid-cols-2">
            <Field label={t`Initial weight (g)`}><input className="desk-input" type="number" min="0" step="0.01" value={form.initialWeight} onChange={(e) => setForm({ ...form, initialWeight: e.target.value, remainingWeight: form.remainingWeight || e.target.value })} /></Field>
            <Field label={t`Remaining weight (g)`}><input className="desk-input" type="number" min="0" step="0.01" value={form.remainingWeight} onChange={(e) => setForm({ ...form, remainingWeight: e.target.value })} /></Field>
          </div>
        </>
      ) : (
        <>
          <Field label={t`Printer name`}><input className="desk-input" value={form.printerName} onChange={(e) => setForm({ ...form, printerName: e.target.value })} /></Field>
          <div className="grid gap-2 sm:grid-cols-2"><Field label={t`Model`}><input className="desk-input" value={form.printerModel} onChange={(e) => setForm({ ...form, printerModel: e.target.value })} /></Field><Field label={t`Status`}><select className="desk-input" value={form.printerStatus} onChange={(e) => setForm({ ...form, printerStatus: e.target.value as PrintingForm["printerStatus"] })}><option value="active">{t`Active`}</option><option value="maintenance">{t`Maintenance`}</option><option value="offline">{t`Offline`}</option></select></Field></div>
        </>
      )}
    </div>
  );
}

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <label className="inline-flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /> {label}</label>;
}
