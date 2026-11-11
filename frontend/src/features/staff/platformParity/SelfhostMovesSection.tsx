import { t } from "@lingui/core/macro";
import { useState } from "react";
import { EmptyState, ErrorText, Field, ListRow, Pagination, RelativeTime, Skeleton, StatusPill, type Tone } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "../platformSpaces/ActionDialog";
import { PAGE_SIZE } from "./parityRequest";
import { SelfhostMoveDialog } from "./SelfhostMoveDialog";
import { moveStatusLabels, useMoveDownload, useSelfhostMoves, type MoveAction, type MoveStatus, type SelfhostMove } from "./selfhostMovesApi";

const TONES: Record<MoveStatus, Tone> = {
  requested: "info", approved: "accent", exporting: "warn", exported: "success", rejected: "neutral", failed: "danger", cancelled: "neutral",
};

function Meta({ move }: { move: SelfhostMove }) {
  return <>requested <RelativeTime date={move.requested_at} exact />{move.note ? ` · "${move.note}"` : ""}
    {move.decided_at ? <> {t` · decided `}<RelativeTime date={move.decided_at} exact /></> : null}
    {move.decision_note ? t` · decision note: "${move.decision_note}"` : ""}
    {move.exported_at ? <> {t` · exported `}<RelativeTime date={move.exported_at} exact /></> : null}
    {move.recipient_fingerprint ? t` · key ${move.recipient_fingerprint}` : ""}
    {move.artifact_sha256 ? t` · SHA-256 ${move.artifact_sha256.slice(0, 16)}…` : ""}
    {move.failure_code ? t` · error ${move.failure_code}` : ""}</>;
}

function Buttons({ move, onAction }: { move: SelfhostMove; onAction: (action: MoveAction) => void }) {
  const download = useMoveDownload();
  const space = move.makerspace_name;
  return <div className="flex flex-wrap items-center gap-2">
    <StatusPill label={move.status_label || moveStatusLabels()[move.status]} tone={TONES[move.status] ?? "neutral"} />
    {move.status === "requested" ? <>
      <button type="button" className="desk-button" aria-label={t`Approve the move of ${space}`} onClick={() => onAction("approve")}>{t`Approve…`}</button>
      <button type="button" className="desk-button-danger-outline" aria-label={t`Decline the move of ${space}`} onClick={() => onAction("reject")}>{t`Decline…`}</button>
    </> : null}
    {move.status === "approved" || move.status === "failed" ? <button type="button" className="desk-button"
      onClick={() => onAction("export")}>{move.status === "failed" ? t`Export again…` : t`Export…`}{" "}<span className="sr-only">{space}</span></button> : null}
    {move.status === "exported" && move.has_file ? <button type="button" className="desk-button-primary" disabled={download.isPending}
      onClick={() => download.mutate(move.id, {
        onError: error => toast(actionErrorText(error), { tone: "error" }) })}>{download.isPending ? t`Preparing…` : t`Download`}{" "}<span className="sr-only">{space}</span></button> : null}
    {move.has_file ? <button type="button" className="desk-button-danger-outline"
      onClick={() => onAction("discard")}>{t`Delete file…`}{" "}<span className="sr-only">{space}</span></button> : null}
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
      {t`The export is encrypted to the new server's encryption key (starts with age1). Downloads use a one-use link that lasts five minutes.`}</p>
    <Field label={t`Status`} className="sm:max-w-64">
      <select className="desk-input" value={status} onChange={event => { setStatus(event.target.value as MoveStatus | ""); setPage(1); }}>
        <option value="">{t`Every status`}</option>
        {(Object.entries(moveStatusLabels()) as [MoveStatus, string][]).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select>
    </Field>
    {list.isLoading ? <Skeleton className="h-24 w-full" />
      : list.isError ? <ErrorText resource={t`move requests`} onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={status ? t`No move requests with this status.` : t`No space has asked to move yet.`} />
      : <div className="grid gap-3">{rows.map(move => <ListRow key={move.id} title={move.makerspace_name} meta={<Meta move={move} />}
        right={<Buttons move={move} onAction={action => setActing({ move, action })} />} />)}</div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    {acting ? <SelfhostMoveDialog move={acting.move} action={acting.action} onClose={() => setActing(null)} /> : null}
  </div>;
}
