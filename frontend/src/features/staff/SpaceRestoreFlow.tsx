import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlowLayout } from "../../components/layouts";
import { Callout, ErrorText, StatusPill } from "../../components/ui";
import { abortSpaceRestore, confirmSpaceRestore, getSpaceRestore, type SpaceRestore } from "./spaceRestoreApi";

const STEP: Record<SpaceRestore["stage"], string> = {
  requested: "preview", staging: "preview", preview_ready: "confirm", applying: "progress",
  completed: "progress", failed: "progress", aborted: "progress",
};

/** Preview -> confirm (re-authentication + typed slug) -> live progress, for one restore. */
export function SpaceRestoreFlow({ restoreId, onClose }: { restoreId: string; onClose: () => void }) {
  const client = useQueryClient();
  const [slug, setSlug] = useState("");
  const query = useQuery({ queryKey: ["space-restore", restoreId], queryFn: () => getSpaceRestore(restoreId),
    refetchInterval: (state) => (["completed", "failed", "aborted"].includes(state.state.data?.stage ?? "") ? false : 2000) });
  const refresh = (data: SpaceRestore) => { client.setQueryData(["space-restore", restoreId], data); return client.invalidateQueries({ queryKey: ["space-restores", data.makerspace] }); };
  const confirm = useMutation({ mutationFn: () => confirmSpaceRestore(restoreId, slug), onSuccess: refresh });
  const abort = useMutation({ mutationFn: () => abortSpaceRestore(restoreId), onSuccess: refresh });
  const op = query.data;
  const step = op ? STEP[op.stage] : "preview";
  const steps = [{ key: "preview", label: "Preview" }, { key: "confirm", label: "Confirm" }, { key: "progress", label: "Restore" }]
    .map((item, index, all) => ({ ...item, state: item.key === step ? "current" as const
      : all.findIndex(entry => entry.key === step) > index ? "done" as const : "todo" as const }));
  const canConfirm = op?.stage === "preview_ready" && !op.blocked && slug === op.makerspace_slug;
  const next = op?.stage === "preview_ready"
    ? { label: "Restore this space", tone: "danger" as const, disabled: !canConfirm, pending: confirm.isPending, pendingLabel: "Starting…",
        disabledReason: op.blocked ? "Rows outside this space would dangle; resolve them first." : "Type the space's slug to confirm.", onClick: () => confirm.mutate() }
    : { label: "Close", onClick: onClose, disabled: false };
  return <FlowLayout presentation="dialog" open title={op ? `Restore ${op.makerspace_name}` : "Restore a space"}
    subject="Nothing changes until you confirm. A safety backup of the space as it is now is taken first."
    state={query.isError ? { status: "error", error: "Could not load this restore.", onRetry: () => { void query.refetch(); } } : { status: op ? "ready" : "loading" }}
    current={step} steps={steps} onCancel={onClose}
    work={op ? <RestoreWork op={op} slug={slug} onSlug={setSlug} /> : null}
    error={confirm.error || abort.error ? { size: "inline", tone: "danger", lead: "That did not work.", body: (confirm.error ?? abort.error)!.message } : undefined}
    footer={{ next, back: ["requested", "staging", "preview_ready"].includes(op?.stage ?? "")
      ? { label: "Cancel this restore", onClick: () => abort.mutate(), pending: abort.isPending, pendingLabel: "Cancelling…" } : undefined }} />;
}

function RestoreWork({ op, slug, onSlug }: { op: SpaceRestore; slug: string; onSlug: (value: string) => void }) {
  const preview = op.preview;
  if (op.stage === "requested" || op.stage === "staging") return <p role="status" className="text-sm text-muted">Preparing the preview…</p>;
  if (op.stage === "applying") return <div role="status" className="grid gap-3">
    <StatusPill label={`Restoring · ${op.progress.percent ?? 0}%`} tone="warn" />
    <progress className="w-full" max={100} value={op.progress.percent ?? 0} aria-label="Restore progress" />
    <p className="text-sm text-muted">Step: {(op.progress.step ?? "queued").replace(/_/g, " ")}. Members cannot change this space until it finishes.</p>
  </div>;
  if (op.stage === "completed") return <Callout size="panel" tone="success" lead="Restored." body={`${op.makerspace_name} is back at its restore point. ${op.report.money_after_restore_point?.length ?? 0} payment record(s) made after it were kept for review; ${op.report.objects_restored ?? 0} file(s) were restored.`} />;
  if (op.stage === "failed") return <ErrorText message={`${op.error_detail} Nothing was changed.`} />;
  if (op.stage === "aborted") return <p className="text-sm text-muted">This restore was cancelled.</p>;
  return <div className="grid gap-4 text-sm">
    <p>Restore point taken {preview.snapshot_at ? new Date(preview.snapshot_at).toLocaleString() : "—"}. {preview.totals?.removed_rows ?? 0} records created since then go; {preview.totals?.added_rows ?? 0} deleted since then come back. Memberships: {preview.memberships?.removed ?? 0} removed, {preview.memberships?.restored ?? 0} restored.</p>
    <p>Kept and flagged “after the restore point”: {preview.money_after_restore_point?.length ?? 0} payment record(s). {preview.evidence_after_restore_point ?? 0} newer evidence photo(s) stay as orphaned records. The live audit history is kept.</p>
    <p>Accounts are never changed: {preview.accounts?.reattributed ?? 0} reference(s) go to the space's anonymous principal and {preview.accounts?.erased_since ?? 0} deleted account(s) stay erased. {preview.inbound_relinked ?? 0} row(s) in other spaces re-link to restored records.</p>
    {op.blocked ? <Callout size="inline" tone="danger" lead="This restore is blocked." body={`${preview.blocking_count ?? 0} row(s) outside this space would point at records the restore removes.`} /> : null}
    <details><summary className="min-h-11 cursor-pointer py-2">What changes, by record type</summary>
      <ul className="grid gap-1">{preview.models?.filter(row => row.removed || row.added).map(row =>
        <li key={row.label} className="tabular-nums">{row.label}: {row.live} now → {row.archived}</li>)}</ul></details>
    <label className="grid gap-2">Type <code>{op.makerspace_slug}</code> to confirm
      <input className="desk-input" autoComplete="off" value={slug} onChange={event => onSlug(event.target.value)} /></label>
  </div>;
}
