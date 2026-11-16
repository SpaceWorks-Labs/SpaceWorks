// "Cards from a CSV" (decision 344(b)): check a CSV of merge values against the design (dry run: which columns fill a
// data field, which are ignored, the first cards drawn by the server from the published version), then print every row
// on the PUBLISHED design: preview and PDF come from the same version and renderer.
import { useMutation } from "@tanstack/react-query";
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { staffRequest, staffRequestBlob } from "../../lib/api";
import { BoxArt } from "../BoxSpinner";
import { ErrorText } from "../ui/ErrorText";
import { Modal } from "../ui/Modal";
import type { CardDesign } from "./cardTypes";
import { saveBlob } from "./designerHistoryApi";
import { SelectInput, Toggle } from "./inspectorFields";

export type CsvReport = { columns: string[]; unknown_columns: string[]; rows: number; preview: Record<string, string>[]; published: boolean;
  /** The first cards rendered by the server from the PUBLISHED version (decision 345(e)). */ images: string[] };
type Paper = "a4" | "letter" | "per_card";
const MAX_BYTES = 256 * 1024;

export function CsvMergeDialog({ design, open, onClose }: { design: CardDesign; open: boolean; onClose: () => void }) {
  const [csv, setCsv] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);
  const [paper, setPaper] = useState<Paper>("a4");
  const [cropMarks, setCropMarks] = useState(true);
  const url = `/admin/card-designs/${design.id}/csv-merge`;
  const check = useMutation({ mutationFn: (text: string) => staffRequest<CsvReport>(url, {
    method: "POST", body: JSON.stringify({ csv: text, dry_run: true }) }) });
  const print = useMutation({
    mutationFn: async () => saveBlob(await staffRequestBlob(url, { method: "POST",
      body: JSON.stringify({ csv, dry_run: false, paper, crop_marks: cropMarks }) }), `card-design-${design.id}-csv.pdf`),
  });
  const report = check.data;
  async function readFile(file: File) {
    setFileError(null);
    if (file.size > MAX_BYTES) { setFileError(t`A CSV merge takes at most 256 KB.`); return; }
    const text = await file.text();
    setCsv(text);
    check.mutate(text);
  }
  const footer = <div className="flex flex-wrap justify-end gap-2">
    <button type="button" className="desk-button-ghost min-h-11" onClick={onClose}>{t`Close`}</button>
    <button type="button" className="desk-button min-h-11" disabled={!report?.rows || !report.published || print.isPending}
      onClick={() => print.mutate()}>{print.isPending ? <><BoxArt size={16} mono />{t`Making the PDF…`}</> : t`Print ${report?.rows ?? 0} cards`}</button>
  </div>;
  return <Modal open={open} onClose={onClose} title={t`Cards from a CSV file`} footer={footer} size="xl">
    <div className="grid gap-4">
      <p className="text-sm text-muted">{t`The first row names the data fields (name, role, number, valid_until, first_name, field:… ), then one row per card, up to 200. These cards have no record in Space Works: their check and desk QR codes stay empty and photos print initials. Use member or staff cards when you need those.`}</p>
      <label className="desk-button min-h-11 cursor-pointer justify-self-start">
        {t`Choose a CSV file`}
        <input type="file" accept=".csv,text/csv" className="sr-only" onChange={(event) => {
          const file = event.target.files?.[0]; event.target.value = ""; if (file) void readFile(file);
        }} />
      </label>
      {fileError ? <ErrorText message={fileError} /> : null}
      {check.isPending ? <p role="status" className="text-sm text-muted">{t`Checking the file…`}</p> : null}
      {check.error ? <ErrorText message={check.error.message} /> : null}
      {report ? <section className="grid gap-3" aria-label={t`What the file gives`}>
        <p className="text-sm text-ink">{t`${report.rows} cards. Fields filled: ${report.columns.join(", ") || "none"}.`}</p>
        {report.unknown_columns.length ? <p className="text-sm text-warn-ink">{t`Ignored columns (not a data field): ${report.unknown_columns.join(", ")}.`}</p> : null}
        {report.published ? null : <p role="alert" className="text-sm text-danger">{t`Publish the design first: a CSV run prints the published version.`}</p>}
        {report.images.length ? <p className="text-xs text-muted">{t`The first cards, drawn from the published version exactly as the PDF prints them.`}</p> : null}
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3" aria-label={t`First cards`}>
          {report.images.map((image, index) => <li key={index} className="grid gap-1">
            <img src={image} alt={t`Card for ${report.preview[index]?.name || t`row ${index + 1}`}`} className="w-full rounded-control border border-line" />
            <span className="truncate text-xs text-muted">{report.preview[index]?.name || t`Card ${index + 1}`}</span>
          </li>)}
        </ul>
        <div className="grid gap-2 sm:grid-cols-2">
          <SelectInput label={t`Paper`} value={paper} onChange={(value) => setPaper(value as Paper)}
            options={[{ value: "a4", label: t`A4 sheets` }, { value: "letter", label: t`Letter sheets` }, { value: "per_card", label: t`One card per page (PVC printer)` }]} />
          <Toggle label={t`Crop marks`} checked={cropMarks && paper !== "per_card"} disabled={paper === "per_card"} onChange={setCropMarks} />
        </div>
      </section> : null}
      {print.error ? <ErrorText message={print.error.message} /> : null}
    </div>
  </Modal>;
}
