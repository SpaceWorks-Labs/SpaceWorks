// Batch print preview: before a "Print sheet" job is queued, the server draws the first sheet
// (fronts and backs) with the same filter, paper and order, and says how many sheets the job
// will print. "Start print job" then queues the existing bulk_sheet job with those settings.
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { Toggle } from "../../components/card-designer/inspectorFields";
import { ErrorBlock } from "../../components/ui/ErrorBlock";
import { Modal } from "../../components/ui/Modal";
import { SegmentedControl } from "../../components/ui/SegmentedControl";
import { Skeleton } from "../../components/ui/Skeleton";
import { staffRequest } from "../../lib/api";
import { plural } from "../../lib/plural";
import { useStartCardJob } from "./cardJobs";

export type SheetFilter = { status?: "active" | "all"; card_ids?: number[]; plan_id?: number; expiring_within_days?: number };
export type SheetPaper = "a4" | "letter";
export type SheetOrder = "duplex" | "fronts_then_backs";
export type SheetPreview = { total: number; per_page: number; sheets: number; paper: SheetPaper; order: SheetOrder;
  front: string | null; back: string | null; mixed_sizes: boolean };

const PAPER_LABEL: Record<SheetPaper, string> = { a4: "A4", letter: "Letter" };

export function sheetSummary(preview: SheetPreview) {
  if (!preview.total) return "No cards match, so there is nothing to print.";
  const sheets = plural(preview.sheets, "sheet");
  return `${plural(preview.total, "card")} on ${sheets}${preview.back ? ` (+ ${plural(preview.sheets, "back")})` : ""}.`;
}

export function SheetPreviewDialog({ open, onClose, previewPath, jobsPath, filter, title = "Print sheet" }: {
  open: boolean; onClose: () => void; previewPath: string; jobsPath: string; filter: SheetFilter; title?: string;
}) {
  const [paper, setPaper] = useState<SheetPaper>("a4");
  const [order, setOrder] = useState<SheetOrder>("duplex");
  const [cropMarks, setCropMarks] = useState(true);
  const settings = { ...filter, paper, order, crop_marks: cropMarks };
  const preview = useQuery({
    queryKey: ["card-sheet-preview", previewPath, settings], enabled: open, retry: false, staleTime: 60_000,
    placeholderData: keepPreviousData,
    queryFn: () => staffRequest<SheetPreview>(previewPath, { method: "POST", body: JSON.stringify(settings) }),
  });
  const start = useStartCardJob(jobsPath);
  const data = preview.data;
  const close = () => { start.reset(); onClose(); };
  const backAlt = order === "duplex"
    ? "The same sheet's backs, mirrored so each back lands behind its front when printed on both sides along the long edge."
    : "The backs for the same cards, printed after all the fronts.";
  return <Modal open={open} onClose={close} title={title} size="xl" footer={<div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
    <button type="button" className="desk-button min-h-11" onClick={close}>Cancel</button>
    <button type="button" className="desk-button-primary min-h-11" disabled={!data?.total || preview.isFetching || start.isPending}
      onClick={() => start.mutate({ kind: "bulk_sheet", ...settings }, { onSuccess: close })}>
      {start.isPending ? "Starting…" : "Start print job"}</button>
  </div>}>
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <SegmentedControl label="Paper" value={paper} onChange={(value) => setPaper(value as SheetPaper)}
          options={[{ value: "a4", label: "A4" }, { value: "letter", label: "Letter" }]} />
        <SegmentedControl label="Print order" value={order} onChange={(value) => setOrder(value as SheetOrder)}
          options={[{ value: "duplex", label: "Both sides" }, { value: "fronts_then_backs", label: "Fronts, then backs" }]} />
        <Toggle label="Crop marks" checked={cropMarks} onChange={setCropMarks} />
      </div>
      <p className="text-xs text-muted">{order === "duplex" ? "For printers that print both sides: each back sheet follows its front sheet."
        : "For one-sided printers: all fronts first, then turn the stack over for the backs."}</p>
      {preview.isLoading ? <Skeleton className="h-72 w-full" /> : null}
      {preview.isError ? <ErrorBlock error={preview.error} resource="sheet preview" onRetry={() => void preview.refetch()} /> : null}
      {data ? <div className="grid gap-3" aria-busy={preview.isFetching}>
        <p role="status" className="text-sm font-semibold text-ink">{sheetSummary(data)}
          {data.total ? <span className="font-normal text-muted"> Up to {data.per_page} cards fit on each {PAPER_LABEL[data.paper]} sheet.</span> : null}</p>
        {data.mixed_sizes ? <p className="rounded-control border border-warn bg-warn-soft p-2 text-sm text-warn-ink">
          Some cards use a different card size. They print on their own sheets, so the job has more sheets than shown here.</p> : null}
        <div className="grid gap-3 md:grid-cols-2">
          {data.front ? <figure className="grid gap-1">
            <img src={data.front} className="mx-auto max-h-[60vh] w-auto max-w-full rounded-control border border-line bg-white"
              alt={`The first ${PAPER_LABEL[data.paper]} sheet of card fronts${cropMarks ? ", with crop marks" : ""}.`} />
            <figcaption className="text-xs text-muted">Fronts, first sheet</figcaption>
          </figure> : null}
          {data.back ? <figure className="grid gap-1">
            <img src={data.back} className="mx-auto max-h-[60vh] w-auto max-w-full rounded-control border border-line bg-white" alt={backAlt} />
            <figcaption className="text-xs text-muted">Backs, first sheet</figcaption>
          </figure> : null}
        </div>
      </div> : null}
      {start.error ? <ErrorBlock error={start.error} /> : null}
    </div>
  </Modal>;
}
