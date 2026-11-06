import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Field, ListRow, RelativeTime } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import type { Makerspace } from "./shared";
import { OUTCOME_OPTIONS, type ProblemReport, type TriageOutcome } from "./AccountabilityTypes";

export function ProblemReportCard({ row, makerspace, onTriaged }: { row: ProblemReport; makerspace: Makerspace; onTriaged: () => void }) {
  const [outcome, setOutcome] = useState<TriageOutcome>("no_issue");
  const [quantities, setQuantities] = useState<Record<number, string>>({});
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [note, setNote] = useState("");
  const actionable = outcome !== "no_issue";
  const resolutions = actionable
    ? row.items
        .map((item) => ({ item_id: item.id, quantity: Number(quantities[item.id] || 0) }))
        .filter((resolution) => resolution.quantity > 0)
    : [];
  const triage = useMutation({
    mutationFn: () => staffRequest(`/admin/makerspace/${makerspace.id}/problem-reports/${row.id}/triage`, {
      method: "POST",
      body: JSON.stringify({ outcome, resolutions, note }),
    }),
    onSuccess: onTriaged,
  });

  return (
    <div className="grid gap-3 rounded-md border border-line bg-surface p-3 text-sm">
      <ListRow title={row.label || "(tool)"} identity={{ kind: "avatar", name: row.requester_username, seed: row.requester_username }}
        meta={<>{row.requester_username} · <RelativeTime date={row.created_at} /><span className="mt-1 block line-clamp-2">{row.note}</span></>} />
      <button className="desk-button-ghost w-fit" aria-expanded={detailsOpen} onClick={() => setDetailsOpen(!detailsOpen)}>{t`Problem details`}</button>
      {detailsOpen ? <p className="whitespace-pre-wrap break-words">{row.note}</p> : null}
      <div className="flex flex-wrap gap-2">
        {OUTCOME_OPTIONS.map((option) => (
          <label key={option.value} className="flex min-h-11 items-center gap-2 rounded-md border border-line bg-bg px-2 py-1 text-xs text-ink">
            <input type="radio" name={`problem-outcome-${row.id}`} value={option.value} checked={outcome === option.value} onChange={() => setOutcome(option.value)} />
            {option.label}
          </label>
        ))}
      </div>
      {actionable ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {row.items.map((item) => (
            <label key={item.id} className="eyebrow grid gap-1">
              <span>{item.product_name} ({item.issued_quantity})</span>
              <input
                className="desk-input"
                type="number"
                min={0}
                max={item.issued_quantity}
                value={quantities[item.id] ?? ""}
                onChange={(event) => setQuantities((current) => ({ ...current, [item.id]: event.target.value }))}
                placeholder="0"
              />
            </label>
          ))}
        </div>
      ) : null}
      <Field label={t`Triage note`}><textarea className="desk-input min-h-20" value={note} onChange={(event) => setNote(event.target.value)} /></Field>
      {actionable && resolutions.length === 0 ? <p className="text-sm text-muted">{t`Choose at least one item quantity to save this outcome.`}</p> : null}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {triage.error ? <p className="text-sm text-danger">{(triage.error as Error).message}</p> : <span />}
        <button className="desk-button-primary" type="button" disabled={triage.isPending || (actionable && resolutions.length === 0)} onClick={() => triage.mutate()}>
          {triage.isPending ? t`Saving…` : t`Save triage`}
        </button>
      </div>
    </div>
  );
}
