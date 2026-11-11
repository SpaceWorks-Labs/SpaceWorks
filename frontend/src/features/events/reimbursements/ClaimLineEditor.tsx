import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Field } from "../../../components/ui/Field";
import { MinorAmountInput } from "../../forms/MinorAmountInput";
import { ItineraryInput } from "../../forms/ItineraryInput";
import { FileInput, type UploadFormFiles } from "../../forms/FileInput";
import type { Category, ClaimLine } from "./types";
import { travelCategoryLabel } from "./labels";

export function newClaimLine(currency: string, category: Category): ClaimLine {
  return { line_uuid: crypto.randomUUID(), category, vendor: "", description: "", traveller: "", expense_date: "",
    original_amount_minor: 0, original_currency: currency, fx_rate: "1", rate_date: "", rate_source: "receipt", source_note: "", route: {}, receipt: null };
}
export function ClaimLineEditor({ line, categories, onChange, upload, onRemove, readOnly }: {
  line: ClaimLine; categories: Category[]; onChange: (value: ClaimLine) => void; upload: UploadFormFiles; onRemove: () => void; readOnly: boolean;
}) {
  const [total, setTotal] = useState(line.receipt?.receipt_total_minor ?? 0);
  const text = (key: "vendor" | "description" | "traveller" | "expense_date" | "rate_date" | "source_note", label: string, type = "text", maxLength = 500) => <Field label={label} key={key}>
    <input className="desk-input" type={type} required={key !== "source_note"} maxLength={maxLength} value={line[key]} onChange={event => onChange({ ...line, [key]: event.target.value })} /></Field>;
  return <fieldset disabled={readOnly} className="grid min-w-0 gap-4 rounded-2xl border border-line bg-panel p-5"><legend className="px-1 font-semibold">{t`Expense`}</legend>
    <Field label={t`Category`}><select className="desk-input" value={line.category} onChange={event => onChange({ ...line, category: event.target.value as Category })}>{categories.map(category => <option key={category} value={category}>{travelCategoryLabel(category)}</option>)}</select></Field>
    <div className="grid gap-4 md:grid-cols-2">{text("vendor", t`Vendor`)}{text("traveller", t`Traveller`, "text", 200)}{text("description", t`Expense description`, "text", 2000)}{text("expense_date", t`Expense date`, "date")}</div>
    <Field label={t`Original amount (${line.original_currency})`} hint={t`For example 12.50, as printed on the receipt.`}><MinorAmountInput required currency={line.original_currency} value={line.original_amount_minor || null} onChange={minor => onChange({ ...line, original_amount_minor: minor ?? Number.NaN })} /></Field>
    <Field label={t`Original currency`} hint={t`Use the currency printed on the receipt.`}><input className="desk-input" required pattern="[A-Z]{3}" maxLength={3} value={line.original_currency} onChange={event => onChange({ ...line, original_currency: event.target.value.toUpperCase() })} /></Field>
    <div className="grid gap-4 md:grid-cols-2"><Field label={t`FX rate to award currency`} hint={t`Award currency units per original currency unit. Use 1 for the same currency.`}><input className="desk-input" inputMode="decimal" required pattern="(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,12})?" value={line.fx_rate} onChange={event => onChange({ ...line, fx_rate: event.target.value })} /></Field>
      {text("rate_date", t`Exchange-rate date`, "date")}
      <Field label={t`Rate source`}><select className="desk-input" value={line.rate_source} onChange={event => onChange({ ...line, rate_source: event.target.value as ClaimLine["rate_source"] })}><option value="receipt">{t`Receipt`}</option><option value="manual">{t`Manual`}</option></select></Field>{text("source_note", t`Exchange-rate source note`)}</div>
    {line.category === "lodging" ? <div className="grid gap-4 md:grid-cols-3">
      <Field label={t`Lodging starts`}><input className="desk-input" required type="date" value={line.lodging_starts_on ?? ""} onChange={event => onChange({ ...line, lodging_starts_on: event.target.value })} /></Field>
      <Field label={t`Lodging ends`}><input className="desk-input" required type="date" value={line.lodging_ends_on ?? ""} onChange={event => onChange({ ...line, lodging_ends_on: event.target.value })} /></Field>
      <Field label={t`Nights`}><input className="desk-input" required type="number" min={1} max={365} value={line.lodging_nights ?? ""} onChange={event => onChange({ ...line, lodging_nights: event.target.valueAsNumber })} /></Field></div>
      : <ItineraryInput question={{ id: `route-${line.line_uuid}`, type: "itinerary", label: t`Expense route`, itinerary: { modes: ["rail", "air", "bus", "car", "other"] } }} value={line.route} onChange={route => onChange({ ...line, route: route as ClaimLine["route"] })} />}
    <Field label={t`Receipt total (${line.original_currency})`} hint={t`Enter the full receipt total, even when claiming only a portion.`}><MinorAmountInput required currency={line.original_currency} value={total || null} onChange={minor => {
      const next = minor ?? Number.NaN; setTotal(next); if (line.receipt) onChange({ ...line, receipt: { ...line.receipt, receipt_total_minor: next } });
    }} /></Field>
    <FileInput question={{ id: `receipt-${line.line_uuid}`, type: "file", label: t`Receipt`, required: true, sensitive: true,
      file: { purpose: "reimbursement_receipt", max_files: 1, max_bytes_each: 10485760 } }} value={line.receipt ? [line.receipt] : []}
      upload={upload} onChange={value => { const refs = value as NonNullable<ClaimLine["receipt"]>[];
        onChange({ ...line, receipt: refs[0] ? { ...refs[0], receipt_total_minor: total } : null }); }} />
    <p className="text-sm text-muted">{t`You can see upload status. Only authorized finance staff can read receipt files.`}</p>
    <button type="button" className="desk-button-danger-outline justify-self-start" onClick={onRemove}>{t`Remove expense`}</button>
  </fieldset>;
}
