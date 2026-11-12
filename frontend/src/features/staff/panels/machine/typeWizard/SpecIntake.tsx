import { useState } from "react";

import { IntakeRows, toRow, type Row } from "./IntakeFieldsEditor";
import type { IntakeFieldSpec } from "./templatesApi";

const fromRow = ({ choicesText, ...field }: Row): IntakeFieldSpec => ({ ...field, required: !!field.required,
  ...(field.type === "choice" ? { choices: choicesText.split(",").map(choice => choice.trim()).filter(Boolean) } : { choices: undefined }) });

/** The template's intake questions, edited with the same row editor the live intake screen uses. Rows are kept as typed and pushed up as spec fields. */
export function SpecIntake({ fields, onChange }: { fields: IntakeFieldSpec[]; onChange: (next: IntakeFieldSpec[]) => void }) {
  const [rows, setRows] = useState<Row[]>(() => fields.map(toRow));
  return <IntakeRows rows={rows} setRows={update => { const next = update(rows); setRows(next); onChange(next.map(fromRow)); }} />;
}
