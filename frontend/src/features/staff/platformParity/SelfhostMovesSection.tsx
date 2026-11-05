import { useState } from "react";
import { EmptyState, ErrorText, Field, ListRow, Pagination, RelativeTime, Skeleton, StatusPill, type Tone } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "../platformSpaces/ActionDialog";
import { PAGE_SIZE } from "./parityRequest";
import { SelfhostMoveDialog } from "./SelfhostMoveDialog";
import { MOVE_STATUS_LABELS, useMoveDownload, useSelfhostMoves, type MoveAction, type MoveStatus, type SelfhostMove } from "./selfhostMovesApi";

const TONES: Record<MoveStatus, Tone> = {
  requested: "info", approved: "accent", exporting: "warn", exported: "success", rejected: "neutral", failed: "danger", cancelled: "neutral",
};

function Meta({ move }: { move: SelfhostMove }) {
  return <>requested <RelativeTime date={move.requested_at} exact />{move.note ? ` · "${move.note}"` : ""}
    {move.decided_at ? <> · decided <RelativeTime date={move.decided_at} exact /></> : null}
    {move.decision_note ? ` · decision note: "${move.decision_note}"` : ""}
    {move.exported_at ? <> · exported <RelativeTime date={move.exported_at} exact /></> : null}
    {move.recipient_fingerprint ? ` · key ${move.recipient_fingerprint}` : ""}
    {move.artifact_sha256 ? ` · SHA-256 ${move.artifact_sha256.slice(0, 16)}…` : ""}
    {move.failure_code ? ` · error ${move.failure_code}` : ""}</>;
}

function Buttons({ move, onAction }: { move: SelfhostMove; onAction: (action: MoveAction) => void }) {
  const download = useMoveDownload();
  const space = move.makerspace_name;
  return <div className="flex flex-wrap items-center gap-2">
    <StatusPill label={move.status_label || MOVE_STATUS_LABELS[move.status]} tone={TONES[move.status] ?? "neutral"} />
    {move.status === "requested" ? <>
      <button type="button" className="desk-button" aria-label={`Approve the move of ${space}`} onClick={() => onAction("approve")}>Approve…</button>
      <button type="button" className="desk-button-danger-outline" aria-label={`Decline the move of ${space}`} onClick={() => onAction("reject")}>Decline…</button>
    </> : null}
    {move.status === "approved" || move.status === "failed" ? <button type="button" className="desk-button"
      aria-label={`Export ${space}`} onClick={() => onAction("export")}>{move.status === "failed" ? "Export again…" : "Export…"}</button> : null}
    {move.status === "exported" && move.has_file ? <button type="button" className="desk-button-primary" disabled={download.isPending}
      aria-label={`Download the export of ${space}`} onClick={() => download.mutate(move.id, {
        onError: error => toast(actionErrorText(error), { tone: "error" }) })}>{download.isPending ? "Preparing…" : "Download"}</button> : null}
    {move.has_file ? <button type="button" className="desk-button-danger-outline" aria-label={`Delete the export file of ${space}`}
      onClick={() => onAction("discard")}>Delete file…</button> : null}
  </div>;
}

/** Requests from spaces to move to their own server: decide, export to the target's key, hand over the file. */
export function SelfhostMovesSection() {
  const [status, setStatus] = useState<MoveStatus | "">("");
  const [page, setPage] = useState(1);
  const [acting, setActing] = useState<{ move: SelfhostMove; action: MoveAction } | null>(null);
  const list = useSelfhostMoves(status, page);
  const rows = list.data?.results ?? [];
  return <div className="grid gap-4">
    <p className="text-sm text-muted">
      The export is encrypted to the target server's age public key. Downloads use a one-use link that lasts five minutes.
    </p>
    <Field label="Status" className="sm:max-w-64">
      <select className="desk-input" value={status} onChange={event => { setStatus(event.target.value as MoveStatus | ""); setPage(1); }}>
        <option value="">Every status</option>
        {(Object.keys(MOVE_STATUS_LABELS) as MoveStatus[]).map(key => <option key={key} value={key}>{MOVE_STATUS_LABELS[key]}</option>)}
      </select>
    </Field>
    {list.isLoading ? <Skeleton className="h-24 w-full" />
      : list.isError ? <ErrorText resource="move requests" onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={status ? "No move requests with this status." : "No space has asked to move yet."} />
      : <div className="grid gap-3">{rows.map(move => <ListRow key={move.id} title={move.makerspace_name} meta={<Meta move={move} />}
        right={<Buttons move={move} onAction={action => setActing({ move, action })} />} />)}</div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    {acting ? <SelfhostMoveDialog move={acting.move} action={acting.action} onClose={() => setActing(null)} /> : null}
  </div>;
}
