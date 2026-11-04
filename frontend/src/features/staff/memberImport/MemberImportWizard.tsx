import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { FlowLayout } from "../../../components/layouts/FlowLayout";
import { StructuredApiError } from "../../../lib/api";
import {
  lifecycleApi, lifecycleKeys, toCsv, type ImportPreview, type ImportResult,
} from "../membershipLifecycleApi";
import { ImportFilePicker, ImportIntro, ImportMapping, ImportPreviewTable } from "./ImportSteps";
import { SheetLinkField, SourcePicker, sheetLinkProblem, type ImportSource } from "./SheetSource";

const FIELDS: [string, string][] = [
  ["email", "Email (required)"], ["name", "Name"], ["phone", "Phone"], ["member_number", "Member number used before"],
  ["plan", "Plan (name)"], ["starts_on", "Term start"], ["ends_on", "Term end"], ["state_code", "State code"],
  ["gstin", "GSTIN"], ["notes", "Staff notes"], ["record_only", "Record only (yes/no)"],
];
type Step = "upload" | "preview" | "result";

const errorText = (error: unknown) => (error instanceof StructuredApiError ? error.message : "The file could not be read.");

type Input = { source: ImportSource; file: File | null; url: string; sheetSha?: string };

function form(input: Input, mapping: Record<string, string>, recordOnly: number[], skip: number[]) {
  const body = new FormData();
  if (input.source === "google_sheet") {
    body.append("source", "google_sheet");
    body.append("url", input.url.trim());
    if (input.sheetSha) body.append("sheet_sha256", input.sheetSha);
  } else body.append("file", input.file as File);
  body.append("mapping", JSON.stringify(Object.fromEntries(Object.entries(mapping).filter(([, column]) => column))));
  body.append("record_only_rows", JSON.stringify(recordOnly));
  body.append("skip_rows", JSON.stringify(skip));
  return body;
}

/** Map → preview (a dry run) → result, with the result downloadable as CSV (G18, #128 C-13).
 * With `sheetsEnabled` (`membership.import_sheets`, L13) the rows may come from a public Google Sheet. */
export function MemberImportWizard({ makerspaceId, open, onClose, sheetsEnabled = false }: {
  makerspaceId: number; open: boolean; onClose: () => void; sheetsEnabled?: boolean;
}) {
  const client = useQueryClient();
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState<ImportSource>("file");
  const [url, setUrl] = useState("");
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [recordOnly, setRecordOnly] = useState<number[]>([]);
  const [skip, setSkip] = useState<number[]>([]);
  const preview = useMutation({
    mutationFn: () => lifecycleApi.importStep(makerspaceId, "preview", form({ source, file, url }, mapping, [], [])) as Promise<ImportPreview>,
    onSuccess: (data) => { if (!Object.keys(mapping).length) setMapping(data.mapping); setStep("preview"); },
  });
  const apply = useMutation({
    mutationFn: () => lifecycleApi.importStep(makerspaceId, "apply",
      form({ source, file, url, sheetSha: preview.data?.sheet_sha256 }, mapping, recordOnly, skip)) as Promise<ImportResult>,
    onSuccess: () => { setStep("result"); void client.invalidateQueries({ queryKey: lifecycleKeys.imported(makerspaceId) }); },
  });
  const reset = () => { setStep("upload"); setFile(null); setUrl(""); setSource("file"); setMapping({}); setRecordOnly([]); setSkip([]); preview.reset(); apply.reset(); onClose(); };
  const fresh = () => { setMapping({}); preview.reset(); apply.reset(); };
  const sheet = sheetsEnabled && source === "google_sheet";
  const result = apply.data;
  const download = () => {
    if (!result) return;
    const blob = new Blob([toCsv(result.rows, ["row", "email", "action", "status", "reason"])], { type: "text/csv" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `member-import-${result.batch_id}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  };
  const steps = (["upload", "preview", "result"] as Step[]).map((key, index, all) => ({
    key, label: { upload: "Choose and map", preview: "Preview", result: "Result" }[key],
    state: (key === step ? "current" : all.indexOf(step) > index ? "done" : "todo") as "done" | "current" | "todo",
  }));
  const failure = preview.error ?? apply.error;
  return <FlowLayout presentation="dialog" open={open} title="Import members"
    subject={`${sheetsEnabled ? "CSV, Excel or a public Google Sheet" : "CSV or Excel"}, read on the server. Nobody is linked until they accept.`}
    steps={steps} current={step} onCancel={reset} state={{ status: "ready" }}
    leaveGuard={step === "preview" ? "Leave without importing? Nothing has been saved yet." : undefined}
    error={failure ? { size: "inline", tone: "danger", lead: "Import problem", body: errorText(failure) } : undefined}
    result={step === "result" && result ? { tone: "success", title: "Import finished",
      summary: <>Invited {result.counts.invited ?? 0}, record only {result.counts.record_only ?? 0}, updated {result.counts.updated ?? 0}, skipped {result.counts.skipped ?? 0}.</>,
      next: { label: "Done", onClick: reset }, undo: { label: "Download result CSV", onClick: download } } : undefined}
    footer={step === "upload" ? { next: { label: "Preview", pending: preview.isPending, disabled: sheet ? Boolean(sheetLinkProblem(url)) : !file,
      disabledReason: sheet ? "Paste a Google Sheets link first." : "Choose a file first.", onClick: () => preview.mutate() } }
      : { back: { label: "Back", onClick: () => setStep("upload") },
        next: { label: "Import", pending: apply.isPending, disabled: !preview.data?.counts.create && !preview.data?.counts.update,
          disabledReason: "Nothing to import.", onClick: () => apply.mutate() } }}
    work={step === "upload" ? <div className="grid gap-4">
      <ImportIntro />
      {sheetsEnabled ? <SourcePicker value={source} onChange={(next) => { setSource(next); fresh(); }} /> : null}
      {sheet ? <SheetLinkField url={url} onUrl={(next) => { setUrl(next); fresh(); }} />
        : <ImportFilePicker file={file} onFile={(next) => { setFile(next); fresh(); }} />}
    </div>
      : <div className="grid gap-5">
        <ImportMapping fields={FIELDS} headers={preview.data?.headers ?? []} mapping={mapping} onMapping={setMapping}
          pending={preview.isPending} onRefresh={() => preview.mutate()} />
        <ImportPreviewTable preview={preview.data} recordOnly={recordOnly} skip={skip} onRecordOnly={setRecordOnly} onSkip={setSkip} />
      </div>} />;
}
