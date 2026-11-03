// Import people from a CSV: upload -> map columns (auto-mapped) -> preview 20 rows with
// counts -> confirm. Every created person gets an emailed invite; nothing links until they accept.
import { useState } from "react";

import { ErrorBlock } from "../../../components/ui";
import { useImportCommit, useImportPreview, type ImportPreview, type Programme } from "./api";

const REASONS: Record<string, string> = { no_name: "no name", bad_email: "email not valid", duplicate_in_file: "repeated in the file",
  already_in_programme: "already in this programme" };

export function ProgrammeImport({ programme, onDone }: { programme: Programme; onDone: () => void }) {
  const preview = useImportPreview(programme.id);
  const commit = useImportCommit(programme.id);
  const [content, setContent] = useState("");
  const [mapping, setMapping] = useState<Record<string, number | null>>({});
  const [approve, setApprove] = useState(false);
  const data: ImportPreview | undefined = preview.data;
  const fields = [{ key: "name", label: "Name" }, { key: "email", label: "Email" },
    ...programme.form_schema.map((question) => ({ key: `field:${question.key}`, label: question.label }))];

  return <div className="grid max-w-3xl gap-4">
    <label className="grid gap-1 text-sm font-semibold text-ink"><span>CSV file (UTF-8, up to 2 MB)</span>
      <input type="file" accept=".csv,text/csv" className="desk-input" onChange={async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;
        const text = await file.text();
        setContent(text);
        preview.mutate(text, { onSuccess: (result) => setMapping(result.mapping) });
      }} /></label>
    {preview.error ? <ErrorBlock error={preview.error} /> : null}
    {data ? <>
      <fieldset className="grid gap-2 sm:grid-cols-2"><legend className="mb-2 text-sm font-semibold text-ink">Match the columns</legend>
        {fields.map((field) => <label key={field.key} className="grid gap-1 text-xs font-semibold text-muted"><span>{field.label}</span>
          <select className="desk-input min-h-11" value={mapping[field.key] ?? ""}
            onChange={(event) => setMapping({ ...mapping, [field.key]: event.target.value === "" ? null : Number(event.target.value) })}>
            <option value="">Not in the file</option>
            {data.headers.map((header, index) => <option key={index} value={index}>{header}</option>)}
          </select></label>)}
      </fieldset>
      <p className="text-sm text-ink">{data.rows_total} rows: <strong>{data.to_create}</strong> will be added,
        {" "}{data.skipped.length} skipped.</p>
      {data.skipped.length ? <ul className="max-h-32 overflow-y-auto text-xs text-muted">
        {data.skipped.slice(0, 50).map((row) => <li key={row.row}>Row {row.row}: {REASONS[row.reason] ?? row.reason}</li>)}</ul> : null}
      <div className="overflow-x-auto rounded-card border border-line">
        <table className="w-full text-left text-xs"><thead className="bg-surface text-muted"><tr>
          {data.headers.map((header, index) => <th key={index} className="p-2">{header}</th>)}</tr></thead>
          <tbody>{data.rows.map((row, index) => <tr key={index} className="border-t border-line">
            {row.map((cell, cellIndex) => <td key={cellIndex} className="p-2">{cell}</td>)}</tr>)}</tbody></table>
      </div>
      <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
        <input type="checkbox" className="h-5 w-5" checked={approve} onChange={(event) => setApprove(event.target.checked)} />
        Approve everyone added (they get their card once they accept the invite)</label>
      {commit.error ? <ErrorBlock error={commit.error} /> : null}
      {commit.data ? <p role="status" className="text-sm text-success">Added {commit.data.created}. Invites are on their way.</p> : null}
      <div className="flex gap-2">
        <button type="button" className="desk-button-primary min-h-11" disabled={commit.isPending || mapping.name == null || mapping.email == null}
          onClick={() => commit.mutate({ content, mapping, approve }, { onSuccess: onDone })}>
          {commit.isPending ? "Importing…" : `Add ${data.to_create} people`}</button>
      </div>
    </> : null}
  </div>;
}
