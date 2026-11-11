// Batch print preview: before a "Print sheet" job is queued, the server draws the first sheet
// (fronts and backs) with the same filter, paper and order, and says how many sheets the job
// will print. "Start print job" then queues the existing bulk_sheet job with those settings.
import { plural, t } from "@lingui/core/macro";
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { Toggle } from "../../components/card-designer/inspectorFields";
import { ErrorBlock } from "../../components/ui/ErrorBlock";
import { Modal } from "../../components/ui/Modal";
import { SegmentedControl } from "../../components/ui/SegmentedControl";
import { Skeleton } from "../../components/ui/Skeleton";
import { staffRequest } from "../../lib/api";
import { useStartCardJob } from "./cardJobs";

export type SheetFilter = { status?: "active" | "all"; card_ids?: number[]; plan_id?: number; expiring_within_days?: number;
  /** Event cards only. */
  roles?: string[]; checked_in?: boolean | null };
export type SheetPaper = "a4" | "letter";
export type SheetOrder = "duplex" | "fronts_then_backs";
export type SheetPreview = { total: number; per_page: number; sheets: number; paper: SheetPaper; order: SheetOrder;
  front: string | null; back: string | null; mixed_sizes: boolean };

const PAPER_LABEL: Record<SheetPaper, string> = { a4: "A4", letter: t`Letter` };

export function sheetSummary(preview: SheetPreview) {
  if (!preview.total) return t`No cards match, so there is nothing to print.`;
  const cards = plural(preview.total, { one: "# card", other: "# cards" });
  const sheets = plural(preview.sheets, { one: "# sheet", other: "# sheets" });
  const backs = plural(preview.sheets, { one: "# back", other: "# backs" });
  return preview.back ? t`${cards} on ${sheets} (+ ${backs}).` : t`${cards} on ${sheets}.`;
}

export function SheetPreviewDialog({ open, onClose, previewPath, jobsPath, filter, title = t`Print sheet` }: {
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
    <button type="button" className="desk-button min-h-11" onClick={close}>{t`Cancel`}</button>
    <button type="button" className="desk-button-primary min-h-11" disabled={!data?.total || preview.isFetching || start.isPending}
      onClick={() => start.mutate({ kind: "bulk_sheet", ...settings }, { onSuccess: close })}>
      {start.isPending ? t`Starting…` : t`Start print job`}</button>
  </div>}>
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <SegmentedControl label={t`Paper`} value={paper} onChange={(value) => setPaper(value as SheetPaper)}
          options={[{ value: "a4", label: "A4" }, { value: "letter", label: t`Letter` }]} />
        <SegmentedControl label={t`Print order`} value={order} onChange={(value) => setOrder(value as SheetOrder)}
          options={[{ value: "duplex", label: t`Both sides` }, { value: "fronts_then_backs", label: t`Fronts, then backs` }]} />
        <Toggle label={t`Crop marks`} checked={cropMarks} onChange={setCropMarks} />
      </div>
      <p className="text-xs text-muted">{order === "duplex" ? t`For printers that print both sides: each back sheet follows its front sheet.`
        : t`For one-sided printers: all fronts first, then turn the stack over for the backs.`}</p>
      {preview.isLoading ? <Skeleton className="h-72 w-full" /> : null}
      {preview.isError ? <ErrorBlock error={preview.error} resource={t`sheet preview`} onRetry={() => void preview.refetch()} /> : null}
      {data ? <div className="grid gap-3" aria-busy={preview.isFetching}>
        <p role="status" className="text-sm font-semibold text-ink">{sheetSummary(data)}
          {data.total ? <span className="font-normal text-muted"> {t` Up to ${data.per_page} cards fit on each ${PAPER_LABEL[data.paper]} sheet.`}</span> : null}</p>
        {data.mixed_sizes ? <p className="rounded-control border border-warn bg-warn-soft p-2 text-sm text-warn-ink">
          {t`Some cards use a different card size. They print on their own sheets, so the job has more sheets than shown here.`}</p> : null}
        <div className="grid gap-3 md:grid-cols-2">
          {data.front ? <figure className="grid gap-1">
            <img src={data.front} className="mx-auto max-h-[60vh] w-auto max-w-full rounded-control border border-line bg-white"
              alt={cropMarks ? t`The first ${PAPER_LABEL[data.paper]} sheet of card fronts, with crop marks.` : t`The first ${PAPER_LABEL[data.paper]} sheet of card fronts.`} />
            <figcaption className="text-xs text-muted">{t`Fronts, first sheet`}</figcaption>
          </figure> : null}
          {data.back ? <figure className="grid gap-1">
            <img src={data.back} className="mx-auto max-h-[60vh] w-auto max-w-full rounded-control border border-line bg-white" alt={backAlt} />
            <figcaption className="text-xs text-muted">{t`Backs, first sheet`}</figcaption>
          </figure> : null}
        </div>
      </div> : null}
      {start.error ? <ErrorBlock error={start.error} /> : null}
    </div>
  </Modal>;
}
