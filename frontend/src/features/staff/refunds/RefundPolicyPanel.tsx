import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card, Callout, Field, StatusPill } from "../../../components/ui";
import { formatMoney } from "../paymentsApi";
import {
  caseErrorMessage, formatWindow, listRefundPolicies, refundPolicyKey, removeRefundPolicy, saveRefundPolicy,
  type PolicyBody, type RefundPolicy,
} from "./refundsApi";

const AREA_TITLES: Record<RefundPolicy["area"], string> = { events: "Events", bookings: "Bookings" };
const HOURS = 60;

/** Read-only for anyone without manage_makerspace; the API enforces it either way. */
export function RefundPolicyPanel({ makerspaceId, canEdit }: { makerspaceId: number; canEdit: boolean }) {
  const policies = useQuery({ queryKey: refundPolicyKey(makerspaceId), queryFn: () => listRefundPolicies(makerspaceId) });
  if (policies.isLoading) return <p className="text-sm text-muted" role="status">Loading refund policy…</p>;
  if (policies.error || !policies.data) return <Callout size="inline" tone="danger" lead="Couldn't load the refund policy."
    body="Try again in a moment." />;
  return <div className="grid gap-4">
    {policies.data.map((policy) => <PolicyCard key={policy.area} makerspaceId={makerspaceId} policy={policy} canEdit={canEdit} />)}
    <Card>
      <div className="grid gap-3">
        <div className="flex items-center justify-between gap-2">
          <h3 className="title-section">Memberships</h3>
          <StatusPill label="Staff decide" tone="neutral" />
        </div>
        <p className="text-sm text-muted">Cancelling a membership never owes money automatically. A member can ask
          for a refund on a paid membership charge, and you decide each one in the queue.</p>
      </div>
    </Card>
  </div>;
}

function PolicyCard({ makerspaceId, policy, canEdit }: { makerspaceId: number; policy: RefundPolicy; canEdit: boolean }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  // A space with no policy yet starts from a common shape: full refund two days out, half
  // a refund one day out. Nothing is saved until staff press Save.
  const start = policy.configured ? policy : { full_before_minutes: 2880, partial_before_minutes: 1440,
    partial_percent: 50, cancellation_fee: "0.00" };
  const [full, setFull] = useState(String((start.full_before_minutes ?? 0) / HOURS));
  const [partial, setPartial] = useState(String((start.partial_before_minutes ?? 0) / HOURS));
  const [percent, setPercent] = useState(String(start.partial_percent ?? 0));
  const [fee, setFee] = useState(start.cancellation_fee ?? "0.00");
  const [problem, setProblem] = useState<string | null>(null);
  const done = () => { queryClient.invalidateQueries({ queryKey: refundPolicyKey(makerspaceId) }); setEditing(false); };
  const save = useMutation({ mutationFn: (body: PolicyBody) => saveRefundPolicy(makerspaceId, policy.area, body), onSuccess: done });
  const remove = useMutation({ mutationFn: () => removeRefundPolicy(makerspaceId, policy.area), onSuccess: done });
  const submit = () => {
    const body = { full_before_minutes: Math.round(Number(full) * HOURS), partial_before_minutes: Math.round(Number(partial) * HOURS),
      partial_percent: Math.round(Number(percent)), cancellation_fee: fee.trim() || "0" };
    const found = [body.full_before_minutes, body.partial_before_minutes, body.partial_percent].some((value) => !Number.isFinite(value) || value < 0)
      ? "Use whole, non-negative numbers." : body.partial_before_minutes > body.full_before_minutes
        ? "The partial window must end before the full-refund window starts." : body.partial_percent > 100
          ? "A percentage cannot be more than 100." : !/^\d+(\.\d{1,2})?$/.test(body.cancellation_fee) ? "Enter the fee with at most two decimals." : null;
    setProblem(found);
    if (!found) save.mutate(body);
  };
  const error = problem ?? (save.error ? caseErrorMessage(save.error) : remove.error ? caseErrorMessage(remove.error) : null);
  return <Card>
    <div className="grid gap-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="title-section">{AREA_TITLES[policy.area]}</h3>
        <StatusPill label={policy.configured ? "Policy set" : "Staff decide"} tone={policy.configured ? "success" : "neutral"} />
      </div>
      {editing ? <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); submit(); }}>
        <Field label="Full refund if cancelled at least (hours before)"><input className="desk-input" inputMode="numeric" value={full} onChange={(event) => setFull(event.target.value)} /></Field>
        <Field label="Partial refund if cancelled at least (hours before)"><input className="desk-input" inputMode="numeric" value={partial} onChange={(event) => setPartial(event.target.value)} /></Field>
        <Field label="Partial refund (%)"><input className="desk-input" inputMode="numeric" value={percent} onChange={(event) => setPercent(event.target.value)} /></Field>
        <Field label={`Cancellation fee kept (${policy.currency.toUpperCase()})`}><input className="desk-input" inputMode="decimal" value={fee} onChange={(event) => setFee(event.target.value)} /></Field>
        <div className="flex flex-wrap gap-2">
          <button className="desk-button-brand" type="submit" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save policy"}</button>
          <button className="desk-button" type="button" onClick={() => setEditing(false)}>Cancel</button>
        </div>
      </form> : <PolicySummary policy={policy} />}
      {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
      {canEdit && !editing ? <div className="flex flex-wrap gap-2">
        <button className="desk-button" type="button" onClick={() => setEditing(true)}>{policy.configured ? "Edit policy" : "Set a policy"}</button>
        {policy.configured ? <button className="desk-button" type="button" disabled={remove.isPending} onClick={() => remove.mutate()}>Remove</button> : null}
      </div> : null}
    </div>
  </Card>;
}

function PolicySummary({ policy }: { policy: RefundPolicy }) {
  if (!policy.configured) return <p className="text-sm text-muted">No automatic refund. When a paid {policy.area === "events"
    ? "registration" : "booking"} is cancelled, nothing is owed unless you approve a member's request.</p>;
  const fee = Number(policy.cancellation_fee ?? 0) > 0 ? ` A ${formatMoney(policy.cancellation_fee ?? "0", policy.currency)} fee is kept.` : "";
  return <ul className="grid gap-1 text-sm text-muted">
    <li><span className="text-ink">Full refund</span> {formatWindow(policy.full_before_minutes ?? 0)}</li>
    <li><span className="text-ink">{policy.partial_percent}% refund</span> {formatWindow(policy.partial_before_minutes ?? 0)}</li>
    <li>Later than that: no refund.{fee}</li>
    {policy.area === "events" ? <li>An event the space cancels is always refunded in full.</li> : null}
  </ul>;
}
