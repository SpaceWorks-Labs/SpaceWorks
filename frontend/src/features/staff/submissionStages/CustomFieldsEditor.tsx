import { Field } from "../../../components/ui";
import type { CustomField, FieldType, FieldVisibility } from "./types";

const TYPES: Record<FieldType, string> = { short_text: "Short text", long_text: "Long text", choice: "Choice", url: "Link (URL)" };
const VISIBILITY: Record<FieldVisibility, string> = { staff_and_judges: "Staff and judges", staff_only: "Staff only",
  public: "Public (choice fields also filter the gallery)" };

/** #178 custom required fields per stage, with S7 visibility. */
export function CustomFieldsEditor({ value, onChange, label }: { value: CustomField[]; onChange: (next: CustomField[]) => void; label: string }) {
  const update = (index: number, patch: Partial<CustomField>) => onChange(value.map((field, i) => i === index ? { ...field, ...patch } : field));
  return <fieldset className="grid gap-3"><legend className="font-semibold text-ink">{`Questions for ${label}`}</legend>
    {value.map((field, index) => <div key={index} className="grid gap-3 rounded-2xl border border-line p-3 md:grid-cols-2">
      <Field label={`Question ${index + 1}`}><input className="desk-input min-h-11" maxLength={120} value={field.label}
        onChange={e => update(index, { label: e.target.value, ...(field.key ? {} : { key: slug(e.target.value) }) })} /></Field>
      <Field label={`Question ${index + 1} key`} hint="Lowercase letters, numbers and underscores."><input className="desk-input min-h-11"
        maxLength={40} value={field.key} onChange={e => update(index, { key: slug(e.target.value) })} /></Field>
      <Field label={`Question ${index + 1} answer type`}><select className="desk-input min-h-11" value={field.type}
        onChange={e => update(index, { type: e.target.value as FieldType })}>
        {Object.entries(TYPES).map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></Field>
      <Field label={`Who can read question ${index + 1}`}><select className="desk-input min-h-11" value={field.visible_to}
        onChange={e => update(index, { visible_to: e.target.value as FieldVisibility })}>
        {Object.entries(VISIBILITY).map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></Field>
      {field.type === "choice" ? <Field label={`Question ${index + 1} choices`} hint="Separate choices with commas (at least two).">
        <input className="desk-input min-h-11" value={field.choices.join(", ")}
          onChange={e => update(index, { choices: e.target.value.split(",").map(part => part.trim()).filter(Boolean) })} /></Field> : null}
      <Field label={`Question ${index + 1} help`}><input className="desk-input min-h-11" maxLength={300} value={field.help}
        onChange={e => update(index, { help: e.target.value })} /></Field>
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={field.required}
        onChange={e => update(index, { required: e.target.checked })} />Required to submit</label>
      <button type="button" className="desk-button min-h-11 justify-self-start" onClick={() => onChange(value.filter((_, i) => i !== index))}>
        {`Remove question ${index + 1}`}</button>
    </div>)}
    <button type="button" className="desk-button min-h-11 justify-self-start" disabled={value.length >= 20}
      onClick={() => onChange([...value, { key: "", label: "", type: "short_text", required: false, choices: [], help: "", visible_to: "staff_and_judges" }])}>
      Add a question</button>
  </fieldset>;
}

export function slug(text: string) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^[^a-z]+/, "").slice(0, 40).replace(/_+$/, "");
}
