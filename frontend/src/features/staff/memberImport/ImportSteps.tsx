import { t } from "@lingui/core/macro";
import { Field, StatusPill } from "../../../components/ui";
import type { ImportPreview } from "../membershipLifecycleApi";

const REASONS = (): Record<string, string> => ({
  email_invalid: t`Email missing or invalid`, starts_on_invalid: t`Start date not understood`, ends_on_invalid: t`End date not understood`,
  dates_out_of_order: t`End is not after start`, plan_unknown: t`No active plan by that name`, duplicate_email: t`Email repeated in the file`,
  duplicate_phone: t`Phone repeated in the file`, duplicate_member_number: t`Member number already used`,
  already_member: t`Already an active member here`,
});

export function ImportIntro() {
  return <p className="text-sm text-muted">{t`Each row becomes a pending membership. The person gets an emailed invitation and joins by signing in with that email; existing accounts are never linked for them. Rows marked “record only” are kept in the register without an invitation.`}</p>;
}

export function ImportFilePicker({ file, onFile }: { file: File | null; onFile: (file: File | null) => void }) {
  return <div className="grid gap-3">
    <Field label={t`Member file`} hint={t`CSV, TSV or Excel (.xlsx), up to 5 MB and 5,000 rows. The first row holds the column names.`}>
      <input className="desk-input" type="file" accept=".csv,.tsv,.xlsx,text/csv"
        onChange={(event) => onFile(event.target.files?.[0] ?? null)} />
    </Field>
    {file ? <p className="text-sm text-ink">{t`Selected: ${file.name}`}</p> : null}
  </div>;
}

export function ImportMapping({ fields, headers, mapping, onMapping, pending, onRefresh }: {
  fields: [string, string][]; headers: string[]; mapping: Record<string, string>;
  onMapping: (mapping: Record<string, string>) => void; pending: boolean; onRefresh: () => void;
}) {
  return <fieldset className="grid gap-3 sm:grid-cols-2">
    <legend className="title-section mb-2">{t`Match your columns`}</legend>
    {fields.map(([field, label]) => <Field key={field} label={label}>
      <select className="desk-input max-w-full" value={mapping[field] ?? ""}
        onChange={(event) => onMapping({ ...mapping, [field]: event.target.value })}>
        <option value="">{t`Not in the file`}</option>
        {headers.map((header) => <option key={header} value={header}>{header}</option>)}
      </select>
    </Field>)}
    <div className="sm:col-span-2"><button className="desk-button" type="button" disabled={pending} onClick={onRefresh}>
      {pending ? t`Checking…` : t`Check again with these columns`}</button></div>
  </fieldset>;
}

export function ImportPreviewTable({ preview, recordOnly, skip, onRecordOnly, onSkip }: {
  preview?: ImportPreview; recordOnly: number[]; skip: number[];
  onRecordOnly: (rows: number[]) => void; onSkip: (rows: number[]) => void;
}) {
  if (!preview) return null;
  const toggle = (list: number[], row: number) => list.includes(row) ? list.filter((value) => value !== row) : [...list, row];
  return <section aria-label={t`Import preview`} className="grid gap-3">
    <p role="status" className="text-sm text-ink">{t`Dry run: ${preview.counts.create} new, ${preview.counts.update} updated, ${preview.counts.skip} skipped (${preview.total_rows} rows`}{preview.total_rows > preview.rows.length ? t`; showing the first ${preview.rows.length}` : ""}).</p>
    <div className="overflow-x-auto"><table className="w-full min-w-[36rem] text-left text-sm">
      <thead><tr className="text-muted"><th scope="col" className="p-2">{t`Row`}</th><th scope="col" className="p-2">{t`Email`}</th>
        <th scope="col" className="p-2">{t`Outcome`}</th><th scope="col" className="p-2">{t`Record only`}</th><th scope="col" className="p-2">{t`Skip`}</th></tr></thead>
      <tbody>{preview.rows.map((item) => <tr key={item.row} className="border-t border-line">
        <td className="p-2">{item.row}</td><td className="p-2 [overflow-wrap:anywhere]">{String(item.data.email ?? "")}</td>
        <td className="p-2"><StatusPill tone={item.action === "skip" ? "warn" : "success"}
          label={item.action === "skip" ? REASONS()[item.reason] ?? item.reason : item.action === "create" ? t`New` : t`Update`} /></td>
        <td className="p-2"><input className="h-4 w-4" type="checkbox" aria-label={t`Row ${item.row} record only`}
          disabled={item.action !== "create"} checked={recordOnly.includes(item.row) || Boolean(item.data.record_only)}
          onChange={() => onRecordOnly(toggle(recordOnly, item.row))} /></td>
        <td className="p-2"><input className="h-4 w-4" type="checkbox" aria-label={t`Skip row ${item.row}`}
          disabled={item.action === "skip"} checked={skip.includes(item.row)} onChange={() => onSkip(toggle(skip, item.row))} /></td>
      </tr>)}</tbody>
    </table></div>
  </section>;
}
