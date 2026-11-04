import { Field } from "../../../components/ui";
import { KIND_LABELS, type ProductForm } from "./productDraft";
import type { ShopAccess } from "./shopAccess";

/** The product's own fields. Feature-gated fields appear only while their switch is on. */
export function ShopProductFields({ form, onChange, access }: { form: ProductForm; onChange: (patch: Partial<ProductForm>) => void; access: ShopAccess }) {
  const { features } = access;
  const check = (key: "is_public" | "is_active" | "members_only" | "show_exact_stock", label: string, hint?: string) =>
    <label className="flex min-h-11 items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={form[key]}
      onChange={event => onChange({ [key]: event.target.checked })} /><span>{label}{hint ? <span className="block text-muted">{hint}</span> : null}</span></label>;
  return <div className="grid gap-4">
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Name"><input className="desk-input min-h-11" required maxLength={200} value={form.name} onChange={event => onChange({ name: event.target.value })} /></Field>
      <Field label="Kind"><select className="desk-input min-h-11" value={form.kind} onChange={event => onChange({ kind: event.target.value as ProductForm["kind"] })}>
        {Object.entries(KIND_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>
      <Field label="Category" hint="Buyers filter the shop by category."><input className="desk-input min-h-11" value={form.category}
        onChange={event => onChange({ category: event.target.value })} /></Field>
      <Field label="Unit" hint="For example: piece, metre, pack."><input className="desk-input min-h-11" value={form.unit}
        onChange={event => onChange({ unit: event.target.value })} /></Field>
    </div>
    <Field label="Description"><textarea className="desk-input" rows={4} value={form.description} onChange={event => onChange({ description: event.target.value })} /></Field>
    <div className="grid gap-1">
      {check("is_public", "Show on the public shop page", "Off: sold only at the desk.")}
      {check("is_active", "On sale")}
      {features.memberPrices ? check("members_only", "Members only", "Only signed-in members of this space can buy it.") : null}
      {features.publicStock ? check("show_exact_stock", "Show the exact count on the shop page", "Otherwise buyers see In stock, Low or Sold out.") : null}
    </div>
    {features.orderLimits ? <Field label="Most per order" hint="Leave empty for no limit."><input className="desk-input min-h-11 w-32" type="number" min={1}
      value={form.max_per_order} onChange={event => onChange({ max_per_order: event.target.value })} /></Field> : null}
    {features.tax ? <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Tax rate (%)" hint="Prices include this tax. Leave empty to use no tax class."><input className="desk-input min-h-11" inputMode="decimal"
        value={form.tax_percent} onChange={event => onChange({ tax_percent: event.target.value })} /></Field>
      <Field label="HSN code"><input className="desk-input min-h-11" value={form.hsn_code} onChange={event => onChange({ hsn_code: event.target.value })} /></Field>
    </div> : null}
  </div>;
}
