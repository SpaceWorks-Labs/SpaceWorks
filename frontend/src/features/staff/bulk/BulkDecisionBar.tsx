import { t } from "@lingui/core/macro";
import { useId, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Field } from "../../../components/ui";
import { StructuredApiError, staffRequest } from "../../../lib/api";

export const BULK_LIMIT = 50;
export type BulkRow = { id: number; label: string };
export type BulkDecision = { key: string; label: string; needsReason?: boolean; danger?: boolean };
type Result = { decided: number; ids: number[] };

function causeText(cause: unknown): string {
  if (typeof cause === "string") return cause;
  if (Array.isArray(cause)) return cause.map(causeText).filter(Boolean).join(" ");
  if (cause && typeof cause === "object") {
    const record = cause as Record<string, unknown>;
    return typeof record.detail === "string" ? record.detail : Object.values(record).map(causeText).filter(Boolean).join(" ");
  }
  return "";
}

/** Plain words for a refused batch: nothing changed, which row stopped it, and why (the server's 409 `failed_id`). */
export function bulkErrorText(error: unknown, rows: BulkRow[]) {
  if (error instanceof StructuredApiError && error.status === 409 && typeof error.body.failed_id === "number") {
    const id = error.body.failed_id;
    const row = rows.find(item => item.id === id);
    const why = causeText(error.body.cause) || t`It may have been decided already, or you can't decide it.`;
    return t`Nothing was changed. ${row?.label ?? t`Item #${id}`} could not be decided: ${why} Untick it and try again.`;
  }
  return error instanceof Error ? error.message : t`That didn't work. Nothing was changed.`;
}

/**
 * Decision 242 / U5: pick up to 50 waiting items and decide them together. The server treats the batch
 * as all-or-nothing (one transaction, one audit row per item): if any item is refused, none change and
 * the reply names the one that stopped it.
 */
type BarProps = { title: string; rows: BulkRow[]; decisions: BulkDecision[]; path: (decision: string) => string; onDone: () => void };

export function BulkDecisionBar(props: BarProps) {
  // With fewer than two waiting rows there is nothing to batch: render nothing and start no mutation.
  return props.rows.length < 2 ? null : <BulkDecisionPanel {...props} />;
}

function BulkDecisionPanel({ title, rows, decisions, path, onDone }: BarProps) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [picked, setSelected] = useState<number[]>([]);
  // Only rows still on screen are sent: a row decided elsewhere drops out of the list and the batch.
  const selected = picked.filter(value => rows.some(row => row.id === value));
  const [reason, setReason] = useState("");
  const decide = useMutation({
    mutationFn: (decision: string) => staffRequest<Result>(path(decision), { method: "POST", body: JSON.stringify({ ids: selected, reason: reason.trim() }) }),
    onSuccess: () => { setSelected([]); setReason(""); onDone(); },
  });
  const visible = rows;
  const toggle = (rowId: number) => setSelected(current => current.includes(rowId) ? current.filter(value => value !== rowId)
    : current.length >= BULK_LIMIT ? current : [...current, rowId]);
  const allPicked = visible.length > 0 && visible.slice(0, BULK_LIMIT).every(row => selected.includes(row.id));
  const needsReason = decisions.some(decision => decision.needsReason);
  return <div className="mb-4 grid gap-2">
    <button type="button" className="desk-button min-h-11 w-fit" aria-expanded={open} aria-controls={`${id}-panel`}
      onClick={() => setOpen(value => !value)}>{open ? t`Close bulk decisions` : t`Decide several at once`}</button>
    {decide.isSuccess && !open ? <p role="status" className="text-sm text-muted">{t`Done: ${decide.data.decided} decided.`}</p> : null}
    {open ? <fieldset id={`${id}-panel`} className="grid gap-3 rounded-xl border border-line bg-panel p-3">
      <legend className="title-section px-1">{title}</legend>
      <p className="text-sm text-muted">{t`Pick up to ${BULK_LIMIT}. If any one can't be decided, nothing changes and we tell you which one.`}</p>
      <label className="flex min-h-11 items-center gap-2 text-sm font-semibold">
        <input type="checkbox" className="h-4 w-4" checked={allPicked}
          onChange={() => setSelected(allPicked ? [] : visible.slice(0, BULK_LIMIT).map(row => row.id))} />
        {visible.length > BULK_LIMIT ? t`Select the first ${BULK_LIMIT}` : t`Select all ${visible.length}`}
      </label>
      <ul className="grid gap-1 sm:grid-cols-2">{visible.map(row => <li key={row.id}><label className="flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" className="h-4 w-4" checked={selected.includes(row.id)} onChange={() => toggle(row.id)}
          disabled={!selected.includes(row.id) && selected.length >= BULK_LIMIT} />
        <span className="min-w-0 [overflow-wrap:anywhere]">{row.label}</span>
      </label></li>)}</ul>
      {needsReason ? <Field label={t`Reason (shown to the person; needed to decline)`}>
        <input className="desk-input" maxLength={500} value={reason} onChange={event => setReason(event.target.value)} />
      </Field> : null}
      <div className="flex flex-wrap gap-2">{decisions.map(decision => {
        const blocked = !selected.length || decide.isPending || Boolean(decision.needsReason && !reason.trim());
        return <button key={decision.key} type="button" className={decision.danger ? "desk-button-danger min-h-11" : "desk-button-primary min-h-11"}
          disabled={blocked} onClick={() => decide.mutate(decision.key)}>{`${decision.label} (${selected.length})`}</button>;
      })}</div>
      <p role="status" className="text-sm text-muted">{decide.isPending ? t`Deciding ${selected.length}…` : decide.isSuccess ? t`Done: ${decide.data.decided} decided.` : t`${selected.length} selected`}</p>
      {decide.error ? <p role="alert" className="text-sm text-danger">{bulkErrorText(decide.error, rows)}</p> : null}
    </fieldset> : null}
  </div>;
}
