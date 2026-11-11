import { plural, t } from "@lingui/core/macro";
import { useState } from "react";

import { Card, Field, StatusPill } from "../../../components/ui";
import { formatMoney } from "../paymentsApi";
import { caseErrorMessage, formatWindow, type PolicyBody, type RefundPolicy } from "./refundsApi";

const HOURS = 60;
// A space with no policy yet starts from a common shape. Nothing is saved until Save.
const TIMED_START = { full_before_minutes: 2880, partial_before_minutes: 1440, partial_percent: 50,
  full_within_days: 0, partial_mode: "percent" as const, cancellation_fee: "0.00" };
const TERM_START = { full_before_minutes: 0, partial_before_minutes: 0, partial_percent: 50,
  full_within_days: 14, partial_mode: "pro_rata" as const, cancellation_fee: "0.00" };

/** Validate and shape the form; membership terms are measured in days from their start. */
export function policyBody(membership: boolean, form: Record<"full" | "partial" | "percent" | "days" | "fee", string>,
  mode: "percent" | "pro_rata"): [PolicyBody | null, string | null] {
  const whole = (value: string) => (/^\d+$/.test(value.trim()) ? Number(value) : NaN);
  const body: PolicyBody = {
    full_before_minutes: membership ? 0 : Math.round(whole(form.full) * HOURS),
    partial_before_minutes: membership ? 0 : Math.round(whole(form.partial) * HOURS),
    full_within_days: membership ? whole(form.days) : 0, partial_mode: membership ? mode : "percent",
    partial_percent: membership && mode === "pro_rata" ? 0 : whole(form.percent), cancellation_fee: form.fee.trim() || "0",
  };
  const numbers = [body.full_before_minutes, body.partial_before_minutes, body.full_within_days, body.partial_percent];
  if (numbers.some((value) => !Number.isFinite(value))) return [null, "Use whole, non-negative numbers."];
  if ((body.partial_before_minutes ?? 0) > (body.full_before_minutes ?? 0)) {
    return [null, "The partial window must end before the full-refund window starts."];
  }
  if ((body.partial_percent ?? 0) > 100) return [null, "A percentage cannot be more than 100."];
  if (!/^\d+(\.\d{1,3})?$/.test(body.cancellation_fee ?? "")) return [null, "Enter the fee with no more decimals than the currency has."];
  return [body, null];
}

export function RefundPolicyCard({ title, policy, canEdit, saving, removing, saveError, onSave, onRemove, startEditing = false, onCancel }: {
  title: string; policy: RefundPolicy; canEdit: boolean; saving: boolean; removing: boolean; saveError: unknown;
  onSave: (body: PolicyBody, done: () => void) => void; onRemove?: () => void; startEditing?: boolean; onCancel?: () => void;
}) {
  const membership = policy.area === "membership";
  const start = policy.configured ? policy : membership ? TERM_START : TIMED_START;
  const [editing, setEditing] = useState(startEditing);
  const [form, setForm] = useState({
    full: String((start.full_before_minutes ?? 0) / HOURS), partial: String((start.partial_before_minutes ?? 0) / HOURS),
    percent: String(start.partial_percent ?? 0), days: String(start.full_within_days ?? 0), fee: start.cancellation_fee ?? "0.00",
  });
  const [mode, setMode] = useState<"percent" | "pro_rata">(start.partial_mode ?? "percent");
  const [problem, setProblem] = useState<string | null>(null);
  const input = (key: keyof typeof form, label: string, inputMode: "numeric" | "decimal" = "numeric") =>
    <Field label={label}><input className="desk-input" inputMode={inputMode} value={form[key]}
      onChange={(event) => setForm({ ...form, [key]: event.target.value })} /></Field>;
  const submit = () => {
    const [body, found] = policyBody(membership, form, mode);
    setProblem(found);
    if (body) onSave(body, () => setEditing(false));
  };
  const error = problem ?? (saveError ? caseErrorMessage(saveError) : null);
  return <Card>
    <div className="grid gap-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="title-section">{title}</h3>
        <StatusPill label={policy.configured ? t`Policy set` : t`Staff decide`} tone={policy.configured ? "success" : "neutral"} />
      </div>
      {editing ? <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); submit(); }}>
        {membership ? <>
          {input("days", "Full refund if cancelled within (days of the term start)")}
          <Field label={t`After that, until the term ends`}>
            <select className="desk-input" value={mode} onChange={(event) => setMode(event.target.value as "percent" | "pro_rata")}>
              <option value="pro_rata">{t`Refund the unused part of the term`}</option>
              <option value="percent">{t`Refund a fixed percentage`}</option>
            </select>
          </Field>
          {mode === "percent" ? input("percent", "Partial refund (%)") : null}
        </> : <>
          {input("full", "Full refund if cancelled at least (hours before)")}
          {input("partial", "Partial refund if cancelled at least (hours before)")}
          {input("percent", "Partial refund (%)")}
        </>}
        {input("fee", `Cancellation fee kept (${policy.currency.toUpperCase()})`, "decimal")}
        <div className="flex flex-wrap gap-2">
          <button className="desk-button-brand" type="submit" disabled={saving}>{saving ? t`Saving…` : t`Save policy`}</button>
          <button className="desk-button" type="button" onClick={() => { setEditing(false); onCancel?.(); }}>{t`Cancel`}</button>
        </div>
      </form> : <PolicySummary policy={policy} />}
      {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
      {canEdit && !editing ? <div className="flex flex-wrap gap-2">
        <button className="desk-button" type="button" onClick={() => setEditing(true)}>{policy.configured ? t`Edit policy` : t`Set a policy`}</button>
        {policy.configured && onRemove ? <button className="desk-button" type="button" disabled={removing} onClick={onRemove}>{t`Remove`}</button> : null}
      </div> : null}
    </div>
  </Card>;
}

function PolicySummary({ policy }: { policy: RefundPolicy }) {
  const noun = { events: "registration", bookings: "booking", membership: "membership term" }[policy.area];
  if (!policy.configured) return <p className="text-sm text-muted">{t`No automatic refund. When a paid ${noun} is cancelled, nothing is owed unless you approve a member's request.`}</p>;
  const fee = Number(policy.cancellation_fee ?? 0) > 0 ? ` A ${formatMoney(policy.cancellation_fee ?? "0", policy.currency)} fee is kept.` : "";
  if (policy.area === "membership") {
    const days = policy.full_within_days ?? 0;
    return <ul className="grid gap-1 text-sm text-muted">
      <li><span className="text-ink">{t`Full refund`}</span> {days > 0 ? plural(days, { one: "within # day of the term start", other: "within # days of the term start" }) : t`before the term starts`}</li>
      <li><span className="text-ink">{policy.partial_mode === "pro_rata" ? t`The unused part of the term` : t`${String(policy.partial_percent)}% refund`}</span> {t` after that, until the term ends`}</li>
      <li>{t`After the term ends: no refund.${fee}`}</li>
    </ul>;
  }
  return <ul className="grid gap-1 text-sm text-muted">
    <li><span className="text-ink">{t`Full refund`}</span> {formatWindow(policy.full_before_minutes ?? 0)}</li>
    <li><span className="text-ink">{policy.partial_percent}{t`% refund`}</span> {formatWindow(policy.partial_before_minutes ?? 0)}</li>
    <li>{t`Later than that: no refund.${fee}`}</li>
    {policy.area === "events" ? <li>{t`An event the space cancels is always refunded in full.`}</li> : null}
  </ul>;
}
