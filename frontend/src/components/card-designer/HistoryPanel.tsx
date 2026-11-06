// Version history: every saved revision, newest first. Pick one to see it; "Restore this
// version" saves it as a NEW draft (compare-and-swap on the current revision). Publishing
// stays separate, so cards keep the published version until someone publishes.
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { StructuredApiError } from "../../lib/api";
import { Badge } from "../ui/Badge";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { ErrorBlock } from "../ui/ErrorBlock";
import { Pagination } from "../ui/Pagination";
import { RelativeTime } from "../ui/RelativeTime";
import { Skeleton } from "../ui/Skeleton";
import type { CardDesign } from "./cardTypes";
import { fitInside } from "./canvasMath";
import { CardThumbnail } from "./CardThumbnail";
import { designKey } from "./designerApi";
import { restoreRevision, REVISIONS_PAGE_SIZE, revisionsKey, useRevision, useRevisions, type CardRevision } from "./designerHistoryApi";

const REVIEW: Record<Exclude<CardRevision["review"], "">, { label: string; tone: "warn" | "success" | "danger" | "neutral" }> = {
  pending: { label: "Waiting for approval", tone: "warn" }, approved: { label: "Approved", tone: "success" },
  rejected: { label: "Sent back", tone: "danger" }, withdrawn: { label: "Withdrawn", tone: "neutral" },
};

export function HistoryPanel({ designId, canEdit, values, prepare, onRestored, onReload }: {
  designId: number; canEdit: boolean; values: Record<string, string>; prepare: () => Promise<number>;
  onRestored: (design: CardDesign) => void; onReload: () => void;
}) {
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [chosen, setChosen] = useState<number | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const [outcome, setOutcome] = useState<{ tone: "info" | "error" | "conflict"; text: string } | null>(null);
  const list = useRevisions(designId, page);
  const detail = useRevision(designId, chosen);
  const rows = list.data?.results ?? [];
  const row = rows.find((item) => item.revision === chosen) ?? detail.data ?? null;

  async function restore() {
    if (chosen === null) return;
    setPending(true); setOutcome(null);
    try {
      const current = await prepare();
      const design = await restoreRevision(designId, chosen, current);
      client.setQueryData(designKey(designId), design);
      onRestored(design);
      setOutcome({ tone: "info", text: `Version ${chosen} is now your draft. Publish when you are ready.` });
      setChosen(null); setPage(1);
      void client.invalidateQueries({ queryKey: revisionsKey(designId) });
    } catch (error) {
      if (error instanceof StructuredApiError && error.status === 409) setOutcome({ tone: "conflict", text: "Someone else saved this design." });
      else setOutcome({ tone: "error", text: error instanceof Error ? error.message : "That version couldn't be restored." });
    } finally { setPending(false); setConfirming(false); }
  }

  const document = detail.data?.document;
  const thumb = document ? fitInside(220, 150, document.front.page_width_mm, document.front.page_height_mm) : 0;
  const preview = chosen !== null ? <div className="mt-1 grid gap-2 rounded-control border border-line bg-surface p-2" aria-live="polite">
    {detail.isLoading ? <Skeleton className="h-32 w-full" /> : null}
    {detail.isError ? <ErrorBlock error={detail.error} resource="this version" onRetry={() => void detail.refetch()} /> : null}
    {document ? <div className="grid justify-items-center gap-2">
      <CardThumbnail side={document.front} designId={designId} values={values} mono={document.mono}
        watermark={document.watermark} width={thumb}
        label={`Version ${chosen}, front`} />
      {document.back_enabled ? <CardThumbnail side={document.back} designId={designId} values={values} mono={document.mono}
        watermark={document.watermark}
        width={thumb} label={`Version ${chosen}, back`} /> : null}
    </div> : null}
    {canEdit && row && !row.is_current ? <button type="button" className="desk-button-primary min-h-11" disabled={pending || !document}
      onClick={() => setConfirming(true)}>Restore this version</button> : null}
    {row?.is_current ? <p className="text-xs text-muted">This is the version you are editing.</p> : null}
  </div> : null;
  return <div className="grid gap-3">
    <div className="grid gap-1">
      <h3 className="text-sm font-semibold text-ink">Version history</h3>
      <p className="text-sm text-muted">Each save keeps a version. Restoring one makes it a new draft; cards keep the published version until you publish.</p>
    </div>
    {outcome?.tone === "conflict" ? <p role="alert" className="text-sm text-danger">{outcome.text}{" "}
      <button type="button" className="underline" onClick={onReload}>Load their version</button> (your unsaved edits are dropped).</p> : null}
    {outcome && outcome.tone !== "conflict" ? <p role={outcome.tone === "error" ? "alert" : "status"}
      className={`text-sm ${outcome.tone === "error" ? "text-danger" : "text-muted"}`}>{outcome.text}</p> : null}
    {list.isLoading ? <Skeleton className="h-40 w-full" /> : null}
    {list.isError ? <ErrorBlock error={list.error} resource="version history" onRetry={() => void list.refetch()} /> : null}
    {list.data && !rows.length ? <p className="text-sm text-muted">No saved versions yet.</p> : null}
    <ul className="grid gap-1" aria-label="Versions, newest first">
      {rows.map((item) => <li key={item.revision}>
        <button type="button" aria-pressed={chosen === item.revision} onClick={() => setChosen(chosen === item.revision ? null : item.revision)}
          className={`grid min-h-11 w-full gap-1 rounded-control border px-2 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-focus ${chosen === item.revision ? "border-accent-ink bg-accent-soft" : "border-transparent hover:bg-hover"}`}>
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="font-semibold text-ink">Version {item.revision}</span>
            {item.is_current ? <Badge tone="accent">Current</Badge> : null}
            {item.is_published ? <Badge tone="success">Published</Badge> : null}
            {item.review ? <Badge tone={REVIEW[item.review].tone}>{REVIEW[item.review].label}</Badge> : null}
          </span>
          <span className="text-xs text-muted">{item.created_by || "Someone"} · <RelativeTime date={item.created_at} /> · {item.layers} layers</span>
        </button>
        {chosen === item.revision ? preview : null}
      </li>)}
    </ul>
    {list.data ? <Pagination page={page} totalPages={Math.ceil(list.data.count / REVISIONS_PAGE_SIZE)} count={list.data.count}
      pageSize={REVISIONS_PAGE_SIZE} disabled={list.isFetching} onChange={(next) => { setPage(next); setChosen(null); }} /> : null}
    <ConfirmDialog open={confirming} title={`Restore version ${chosen ?? ""}?`} confirmLabel="Restore as a draft" pending={pending}
      message="It replaces what you are editing now as a new draft. Cards keep the published version until you publish."
      onCancel={() => setConfirming(false)} onConfirm={() => void restore()} />
  </div>;
}
