import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ListLayout } from "../../../components/layouts";
import { Field } from "../../../components/ui/Field";
import { Modal } from "../../../components/ui/Modal";
import { commandError, type EventScope } from "../../events/stagedForms/privateQueries";
import { utcInstant } from "../../events/stagedForms/formPayload";
import { reimbursementAdminPath, useAwardCommand, useRequestQueue } from "./api";
import type { AwardCommand, RequestReviewRow } from "./types";
import { BookedTravelActions, type ScreeningRow } from "./TravelAndCrewPool";

export function ReimbursementRequests({ scope }: { scope: EventScope }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<RequestReviewRow | null>(null);
  const query = useRequestQueue(scope, page);
  return <ListLayout header={{ title: t`Support request screening`, subtitle: t`Offer awards within the approved policy and available budget.` }}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: t`Requests could not be loaded.`, onRetry: () => void query.refetch() }}
    isEmpty={query.data?.count === 0} empty={{ message: t`No support requests to review.` }} pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: "rows", rows: query.data?.results.map(row => <article key={row.id} className="grid gap-3 rounded-2xl border border-line bg-panel p-5">
      <h2 className="title-section">{row.owner_label}</h2><p>{t`${row.state} · Estimated ${row.estimated_total_minor} minor units (${row.currency})`}</p>
      <p>{t`Categories: ${row.categories.join(", ")}`}</p><p>{t`Available pool: ${row.pool.available_minor} minor units (${row.pool.currency}). Reserved: ${row.pool.reserved_minor}. Committed: ${row.pool.committed_minor}.`}</p>
      {row.allowed_actions?.includes("request_decide") ? <button type="button" className="desk-button justify-self-start" onClick={() => setSelected(row)}>{t`Review request`}</button> : null}
      <BookedTravelActions scope={scope} row={row as unknown as ScreeningRow} /></article>) }}
    detail={selected && !query.error ? <AwardDecision key={`${selected.id}:${selected.version}`} scope={scope} row={selected} onClose={() => setSelected(null)} /> : null} />;
}
function AwardDecision({ scope, row, onClose }: { scope: EventScope; row: RequestReviewRow; onClose: () => void }) {
  const [outcome, setOutcome] = useState<AwardCommand["outcome"]>("waitlist");
  const [amount, setAmount] = useState("");
  const [tier, setTier] = useState("");
  const [due, setDue] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const mutation = useAwardCommand(scope);
  const dirty = Boolean(reason || amount || tier || due || outcome !== "waitlist");
  return <Modal open title={t`Review ${row.owner_label}`} onClose={() => { if (!mutation.isPending && (!dirty || window.confirm(t`Discard unsaved award decision?`))) onClose(); }}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault();
      try {
        const body: AwardCommand = { expected_version: row.version, expected_award_version: row.expected_award_version,
          expected_pool_version: row.pool.version, outcome, reason_code: reason,
          ...(outcome === "award" ? { amount_minor: Number(amount), currency: row.currency, ...(tier ? { tier } : {}), accept_by: utcInstant(due) } : {}) };
        setError(""); mutation.mutate({ path: `${reimbursementAdminPath(scope)}requests/${row.id}/decide/`, body }, { onSuccess: onClose });
      } catch { setError(t`Enter a valid award deadline.`); }
    }}><p>{t`Available: ${row.pool.available_minor} minor units (${row.currency}). An offer reserves budget; accepting it does not confirm event admission.`}</p>
      <fieldset disabled={mutation.isPending} className="grid gap-4"><legend className="sr-only">{t`Award decision`}</legend>
        <Field label={t`Outcome`}><select className="desk-input" value={outcome} onChange={event => setOutcome(event.target.value as AwardCommand["outcome"])}><option value="waitlist">{t`Waitlist`}</option><option value="decline">{t`Decline`}</option><option value="award">{t`Offer award`}</option></select></Field>
        {outcome === "award" ? <><Field label={t`Award cap (minor units)`}><input className="desk-input" type="number" required min={1} max={9000000000000000} step={1} value={amount} onChange={event => setAmount(event.target.value)} /></Field>
          {row.tiers.length ? <Field label={t`Policy tier`}><select className="desk-input" required value={tier} onChange={event => { setTier(event.target.value); const selected = row.tiers.find(item => item.key === event.target.value); if (selected) setAmount(String(selected.amount_minor)); }}><option value="">{t`Choose a tier`}</option>{row.tiers.map(item => <option key={item.key} value={item.key}>{item.label} · {item.amount_minor}</option>)}</select></Field> : null}
          <Field label={t`Accept by (your local time)`}><input className="desk-input" type="datetime-local" required value={due} onChange={event => setDue(event.target.value)} /></Field></> : null}
        <Field label={t`Decision reason code`}><input className="desk-input" required maxLength={64} pattern="[a-z][a-z0-9_]{0,63}" value={reason} onChange={event => setReason(event.target.value)} /></Field>
        <button type="submit" className="desk-button-primary">{mutation.isPending ? t`Saving…` : t`Confirm decision`}</button></fieldset>
      {error || mutation.error ? <p role="alert">{error || commandError(mutation.error)}</p> : null}
    </form></Modal>;
}
