import { t } from "@lingui/core/macro";
import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { BoxArt } from "../../../../../components/BoxSpinner";
import { LogoLoader } from "../../../../../components/LogoLoader";
import { staffRequest } from "../../../../../lib/api";
import type { IntakeFieldSpec } from "./templatesApi";

const TYPES = (): [IntakeFieldSpec["type"], string][] => [["text", t`Text`], ["number", t`Number`], ["integer", t`Whole number`], ["choice", t`Choice`], ["boolean", t`Yes or no`]];
export type Row = IntakeFieldSpec & { choicesText: string };
export const toRow = (field: IntakeFieldSpec): Row => ({ ...field, choicesText: (field.choices ?? []).join(", ") });
const keyFrom = (label: string) => label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^[^a-z]+|_+$/g, "").slice(0, 40);

/** A problem with the field list in words, or empty. Keys must be unique and a choice field needs choices. */
export function intakeProblem(rows: Row[]): string {
  const keys = new Set<string>();
  for (const row of rows) {
    if (!row.label.trim() || !/^[a-z][a-z0-9_]*$/.test(row.key)) return t`Every field needs a label and a key made of lowercase letters, digits and underscores.`;
    if (keys.has(row.key)) return t`Two fields use the key ${row.key}.`;
    keys.add(row.key);
    if (row.type === "choice" && !row.choicesText.split(",").some(choice => choice.trim())) return t`The choice field ${row.label} needs at least one choice.`;
  }
  return "";
}

export const intakeSchemaFrom = (rows: Row[]) => ({ version: 1, fields: rows.map(({ choicesText, ...field }) => ({ ...field, required: !!field.required,
  ...(field.type === "choice" ? { choices: choicesText.split(",").map(choice => choice.trim()).filter(Boolean) } : { choices: undefined }) })) });

/** The field rows and the "Add a field" button, shared by the live editor and the template spec editor. */
export function IntakeRows({ rows, setRows, extra }: { rows: Row[]; setRows: (update: (current: Row[]) => Row[]) => void; extra?: ReactNode }) {
  const patch = (index: number, change: Partial<Row>) => setRows(current => current.map((row, at) => at === index ? { ...row, ...change } : row));
  return <>
    {rows.map((row, index) => <div key={index} className="grid gap-2 rounded-lg border border-line p-3 sm:grid-cols-2">
      <label className="grid gap-1 text-sm">{t`Label`}<input className="desk-input" value={row.label} maxLength={80}
        onChange={event => patch(index, { label: event.target.value, ...(row.key === keyFrom(row.label) ? { key: keyFrom(event.target.value) } : {}) })} /></label>
      <label className="grid gap-1 text-sm">{t`Key`}<input className="desk-input code-text" value={row.key} onChange={event => patch(index, { key: event.target.value })} /></label>
      <label className="grid gap-1 text-sm">{t`Type`}<select className="desk-input" value={row.type} onChange={event => patch(index, { type: event.target.value as Row["type"] })}>
        {TYPES().map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={!!row.required} onChange={event => patch(index, { required: event.target.checked })} />{t`Required`}</label>
      {row.type === "choice" ? <label className="grid gap-1 text-sm sm:col-span-2">{t`Choices, separated by commas`}<input className="desk-input" value={row.choicesText} onChange={event => patch(index, { choicesText: event.target.value })} /></label> : null}
      {row.type === "number" || row.type === "integer" ? <>
        <label className="grid gap-1 text-sm">{t`Smallest allowed`}<input className="desk-input" type="number" value={row.min ?? ""} onChange={event => patch(index, { min: event.target.value === "" ? undefined : Number(event.target.value) })} /></label>
        <label className="grid gap-1 text-sm">{t`Largest allowed`}<input className="desk-input" type="number" value={row.max ?? ""} onChange={event => patch(index, { max: event.target.value === "" ? undefined : Number(event.target.value) })} /></label></> : null}
      <div className="sm:col-span-2"><button type="button" className="desk-button-danger min-h-11" onClick={() => setRows(current => current.filter((_, at) => at !== index))}>{t`Remove field`}</button></div>
    </div>)}
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button min-h-11" onClick={() => setRows(current => [...current, toRow({ key: "", label: "", type: "text" })])}>{t`Add a field`}</button>
      {extra}</div>
  </>;
}

/** What members are asked when they request a job on this type (the existing structured-intake endpoint). */
export function IntakeFieldsEditor({ makerspaceId, typeId }: { makerspaceId: number; typeId: number }) {
  const client = useQueryClient();
  const path = `/admin/makerspaces/${makerspaceId}/machine-types/${typeId}/intake`;
  const key = ["staff-intake", makerspaceId, typeId];
  const saved = useQuery({ queryKey: key, queryFn: () => staffRequest<{ intake_schema: { fields?: IntakeFieldSpec[] } | null }>(path), retry: false });
  const [rows, setRows] = useState<Row[]>([]);
  useEffect(() => { if (saved.data) setRows((saved.data.intake_schema?.fields ?? []).map(toRow)); }, [saved.data]);
  const save = useMutation({ mutationFn: () => staffRequest(path, { method: "PUT", body: JSON.stringify({ intake_schema: rows.length ? intakeSchemaFrom(rows) : {} }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: key }) });
  const problem = intakeProblem(rows);
  return <section className="grid gap-3" aria-label={t`Intake fields`}>
    <h3 className="title-panel">{t`Questions for the member`}</h3>
    {saved.isLoading ? <LogoLoader label={t`Loading intake fields…`} size={48} className="min-h-16 py-3" /> : null}
    {saved.isError ? <p role="alert" className="text-sm text-danger">{saved.error.message}</p> : null}
    <IntakeRows rows={rows} setRows={setRows} extra={<button type="button" className="desk-button-primary min-h-11" disabled={!!problem || save.isPending} onClick={() => save.mutate()}>
        {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save intake fields`}</button>} />
    {problem ? <p role="status" className="text-sm text-muted">{problem}</p> : null}
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
    {save.isSuccess ? <p role="status" className="text-sm text-success-ink">{t`Intake fields saved.`}</p> : null}
  </section>;
}
