import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ErrorText, Field } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { getJobSession, trackJob } from "../../../components/ui/jobStore";
import {
  fields,
  labelFor,
  mapRow,
  parseDelimited,
  parseFileSample,
  suggestMapping,
  type BulkImportJob,
  type ImportResult,
  type Mapping,
  type RawRow,
} from "./BulkImportHelpers";
import { type Makerspace } from "./shared";
import { FlowLayout } from "../../../components/layouts";
import { ImportSummary, ImportProgress } from "./BulkImportResults";

export function BulkImport({ makerspace }: { makerspace: Makerspace }) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [rawJson, setRawJson] = useState('[{"name":"New Kit","total_quantity":"1","available_quantity":"1"}]');
  const [tableText, setTableText] = useState("");
  const [headers, setHeaders] = useState<string[]>([]);
  const [sourceRows, setSourceRows] = useState<RawRow[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [mapping, setMapping] = useState<Mapping>({});
  const [step, setStep] = useState("upload");
  const [source, setSource] = useState<"table" | "file" | "json">("table");
  const [jobId, setJobId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const syncMutation = useMutation({
    mutationFn: ({ apply, rows }: { apply: boolean; rows: RawRow[] }) =>
      staffRequest<ImportResult>(`/admin/makerspace/${makerspace.id}/inventory/import/${apply ? "apply" : "preview"}`, {
        method: "POST",
        body: JSON.stringify({ rows }),
      }),
    onMutate: () => setJobId(null),
    onSuccess: (_data, variables) => setStep(variables.apply ? "import" : "review"),
  });
  const jobMutation = useMutation({
    onMutate: getJobSession,
    mutationFn: ({ file, mode }: { file: File; mode: "preview" | "apply" }) => {
      const body = new FormData();
      body.append("mode", mode);
      body.append("file", file);
      body.append("mapping", JSON.stringify(mapping));
      return staffRequest<BulkImportJob>(`/admin/makerspace/${makerspace.id}/inventory/import/jobs`, { method: "POST", body });
    },
    onSuccess: (job, _variables, session) => { setStep(job.mode === "apply" ? "import" : "review"); setJobId(job.id); trackJob({ key: `import:${makerspace.id}:${job.id}`, label: `Inventory ${job.mode} #${job.id}`, makerspaceId: makerspace.id, status: job.status, endpoint: `/admin/makerspace/${makerspace.id}/inventory/import/jobs/${job.id}` }, session); },
  });
  const jobQuery = useQuery({
    queryKey: ["bulk-import-job", makerspace.id, jobId],
    queryFn: () => staffRequest<BulkImportJob>(`/admin/makerspace/${makerspace.id}/inventory/import/jobs/${jobId}`),
    enabled: jobId !== null,
    refetchInterval: (query) => isRunning(query.state.data as BulkImportJob | undefined) ? 1000 : false,
  });
  const activeJob = jobQuery.data ?? jobMutation.data;
  const pending = syncMutation.isPending || jobMutation.isPending || isRunning(activeJob);
  const result = activeJob ? activeJob.result && Object.keys(activeJob.result).length ? activeJob.result : undefined : syncMutation.data;
  const mappedRows = () => sourceRows.map((row) => mapRow(row, mapping));

  const submitRows = (apply: boolean, rows: RawRow[]) => {
    setError("");
    syncMutation.mutate({ apply, rows });
  };
  const startFileJob = (mode: "preview" | "apply") => {
    if (!selectedFile) {
      setError("Select a CSV, TSV, or XLSX file first.");
      return;
    }
    setError("");
    jobMutation.mutate({ file: selectedFile, mode });
  };
  const submitJson = (apply: boolean) => {
    try {
      const parsed = JSON.parse(rawJson);
      if (!Array.isArray(parsed) || parsed.some((row) => !row || typeof row !== "object" || Array.isArray(row))) {
        setError("Advanced JSON must be an array of row objects.");
        return;
      }
      submitRows(apply, parsed as RawRow[]);
    } catch {
      setError("Advanced JSON could not be parsed. Check commas, quotes, and brackets.");
    }
  };
  const loadRows = (rows: RawRow[]) => {
    if (!rows.length) {
      setError("No rows were found.");
      return;
    }
    const nextHeaders = Object.keys(rows[0]);
    setSourceRows(rows);
    setHeaders(nextHeaders);
    setMapping(suggestMapping(nextHeaders));
    setStep("map");
    setError("");
  };
  const chooseFile = (file: File) => { setSource("file"); setSelectedFile(file); parseFileSample(file).then(loadRows).catch(() => setError("We couldn't read that file. Save it as CSV or .xlsx and try again.")); };
  const errors = result?.summary?.errors ?? result?.errors?.length ?? 0;
  const finish = step === "import" && !pending && Boolean(result) && activeJob?.status !== "failed";
  const preview = () => selectedFile ? startFileJob("preview") : submitRows(false, mappedRows());
  const apply = () => selectedFile ? startFileJob("apply") : source === "json" ? submitJson(true) : submitRows(true, mappedRows());
  const failure = error || syncMutation.error?.message || jobMutation.error?.message || jobQuery.error?.message || (activeJob?.status === "failed" ? activeJob.error || "Import job failed." : "");
  return <FlowLayout title="Bulk import" subject="Add or update inventory from a spreadsheet. Review every change before importing." standalone={false}
    state={{ status: "ready" }} current={step} steps={[{ key: "upload", label: "Upload" }, { key: "map", label: "Match columns" }, { key: "review", label: "Review" }, { key: "import", label: "Import" }].map((item, index) => ({ ...item, state: item.key === step ? "current" : index < ["upload", "map", "review", "import"].indexOf(step) ? "done" : "todo" }))}
    onCancel={() => { setStep("upload"); setSourceRows([]); setSelectedFile(null); setJobId(null); syncMutation.reset(); jobMutation.reset(); }}
    leaveGuard={sourceRows.length && !finish ? "Leave this import? Your selected file and mapping will be cleared. A running import continues in the background." : undefined}
    footer={{ back: step === "import" && failure && !pending ? { label: "Review and try again", onClick: () => setStep(source === "json" ? "upload" : "map") } : step !== "upload" && step !== "import" ? { label: "Back", disabled: pending, onClick: () => setStep(step === "review" ? source === "json" ? "upload" : "map" : "upload") } : undefined,
      next: { label: step === "upload" ? "Match columns" : step === "map" ? "Preview" : step === "review" ? `Import ${result?.summary?.total ?? sourceRows.length} rows` : "Importing…",
        pending, pendingLabel: step === "review" ? "Importing…" : "Preparing…", disabled: step === "review" ? errors > 0 || !result : step === "import",
        disabledReason: errors ? `Fix ${errors} errors to continue.` : step === "import" ? "Wait for the import to finish." : undefined,
        onClick: () => { if (step === "upload") { if (source === "json") submitJson(false); else if (selectedFile) setStep("map"); else loadRows(parseDelimited(tableText)); } else if (step === "map") preview(); else if (step === "review") { setStep("import"); apply(); } } } }}
    result={finish ? { tone: "success", title: "Import complete", summary: <><p>Your inventory is ready to review.</p>{result ? <ImportSummary result={result} /> : null}</>, next: { label: "View inventory →", href: `/m/${makerspace.slug}/admin/inventory` } } : undefined}
    work={<div className="grid gap-6">
      {step === "upload" ? <>
        <div onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); const file = event.dataTransfer.files[0]; if (file && !pending) chooseFile(file); }}>
        <Field label="Upload CSV or XLSX" hint="Drop a CSV or Excel file here, or choose a file."><input className="desk-input min-h-32 border-dashed" type="file" accept=".csv,.tsv,.xlsx" disabled={pending}
          onChange={event => { const file = event.target.files?.[0]; if (file) chooseFile(file); }} /></Field></div>
        <Field label="Paste table"><textarea className="desk-input min-h-32" value={tableText} onChange={event => { setSource("table"); setSelectedFile(null); setTableText(event.target.value); }} /></Field>
        <details open={advancedOpen} onToggle={event => setAdvancedOpen(event.currentTarget.open)}><summary className="desk-button-ghost">Use JSON instead</summary>
          <Field label="JSON rows"><textarea className="desk-input min-h-32 code-text" value={rawJson} onChange={event => { setSource("json"); setSelectedFile(null); setRawJson(event.target.value); }} /></Field>
          <button className="desk-button" disabled={pending} onClick={() => { setSource("json"); setSelectedFile(null); submitJson(false); }}>Preview JSON</button>
        </details>
      </> : null}
      {step === "map" ? <div className="grid gap-4 sm:grid-cols-2">{fields.map(field => <Field key={field} label={labelFor(field)}><select className="desk-input" value={mapping[field] ?? ""}
        onChange={event => setMapping(current => ({ ...current, [field]: event.target.value || undefined }))}><option value="">Do not import</option>{headers.map(header => <option key={header} value={header}>{header}</option>)}</select></Field>)}</div> : null}
      {pending || activeJob ? <ImportProgress job={activeJob} loading={pending} /> : null}
      {(step === "review" || step === "import") && result ? <ImportSummary result={result} /> : null}
      <ErrorText message={failure} />{jobQuery.error ? <button className="desk-button" onClick={() => { void jobQuery.refetch(); }}>Retry</button> : null}
    </div>} />;
}
function isRunning(job?: BulkImportJob) { return job?.status === "pending" || job?.status === "running"; }
