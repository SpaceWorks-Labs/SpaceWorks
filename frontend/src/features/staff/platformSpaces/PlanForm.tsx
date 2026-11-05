import { useState, type FormEvent } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "./ActionDialog";
import { LIMIT_KEYS, LIMIT_LABELS, useSavePlan, type HostingPlan, type LimitKey, type PlanBody } from "./plansApi";

const MIB = 1024 * 1024;
type Draft = { key: string; name: string; description: string; is_active: boolean; trial_days: string; price: string; currency: string;
  billing_period: PlanBody["billing_period"]; modules: string; limits: Record<LimitKey, string> };

function draftOf(plan?: HostingPlan): Draft {
  const limits = Object.fromEntries(LIMIT_KEYS.map(key => {
    const value = plan?.limits[key];
    return [key, value === null || value === undefined ? "" : String(key === "storage" ? Math.round(value / MIB) : value)];
  })) as Record<LimitKey, string>;
  return { key: plan?.key ?? "", name: plan?.name ?? "", description: plan?.description ?? "", is_active: plan?.is_active ?? true,
    trial_days: String(plan?.trial_days ?? 0), price: plan ? (plan.price_minor / 100).toFixed(2) : "0", currency: plan?.currency ?? "USD",
    billing_period: plan?.billing_period ?? "monthly", modules: (plan?.allowed_modules ?? []).join(", "), limits };
}

/** Create or edit one hosting plan. Empty limits are unlimited; storage is entered in MiB and stored in bytes. */
export function PlanForm({ plan, onDone }: { plan?: HostingPlan; onDone: () => void }) {
  const save = useSavePlan(plan?.id ?? null);
  const [draft, setDraft] = useState(() => draftOf(plan));
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft(current => ({ ...current, [key]: value }));
  const badLimit = LIMIT_KEYS.some(key => draft.limits[key].trim() !== "" && !(Number(draft.limits[key]) >= 0));
  const valid = /^[a-z0-9]+(-[a-z0-9]+)*$/.test(draft.key) && draft.name.trim() && Number(draft.trial_days) >= 0
    && Number(draft.price) >= 0 && /^[A-Za-z]{3}$/.test(draft.currency) && !badLimit;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid || save.isPending) return;
    const limits = Object.fromEntries(LIMIT_KEYS.map(key => {
      const text = draft.limits[key].trim();
      return [key, text === "" ? null : key === "storage" ? Math.round(Number(text) * MIB) : Math.round(Number(text))];
    }));
    save.mutate({ key: draft.key, name: draft.name.trim(), description: draft.description.trim(), is_active: draft.is_active,
      trial_days: Math.round(Number(draft.trial_days)), price_minor: Math.round(Number(draft.price) * 100), currency: draft.currency.toUpperCase(),
      billing_period: draft.billing_period, limits, allowed_modules: draft.modules.split(",").map(item => item.trim()).filter(Boolean) },
    { onSuccess: () => { toast(plan ? "Plan saved." : "Plan created."); onDone(); } });
  };
  return <form className="grid gap-4" aria-label={plan ? `Edit ${plan.name}` : "New plan"} onSubmit={submit} noValidate>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Name"><input className="desk-input" value={draft.name} onChange={event => set("name", event.target.value)} /></Field>
      <Field label="Key" hint="Lowercase letters, numbers and hyphens."><input className="desk-input" value={draft.key} autoCapitalize="none" onChange={event => set("key", event.target.value)} /></Field>
      <Field label="Price"><input className="desk-input" type="number" min={0} step="0.01" value={draft.price} onChange={event => set("price", event.target.value)} /></Field>
      <Field label="Currency"><input className="desk-input" maxLength={3} value={draft.currency} onChange={event => set("currency", event.target.value)} /></Field>
      <Field label="Billing period">
        <select className="desk-input" value={draft.billing_period} onChange={event => set("billing_period", event.target.value as Draft["billing_period"])}>
          <option value="monthly">Monthly</option><option value="yearly">Yearly</option><option value="none">No recurring bill</option>
        </select>
      </Field>
      <Field label="Trial days" hint="0 means no trial."><input className="desk-input" type="number" min={0} value={draft.trial_days} onChange={event => set("trial_days", event.target.value)} /></Field>
    </div>
    <Field label="Description"><textarea className="desk-input min-h-20" value={draft.description} onChange={event => set("description", event.target.value)} /></Field>
    <fieldset className="grid gap-3 sm:grid-cols-3">
      <legend className="mb-1 text-sm font-semibold text-ink">Limits (empty = unlimited)</legend>
      {LIMIT_KEYS.map(key => <Field key={key} label={key === "storage" ? "Storage (MiB)" : LIMIT_LABELS[key]}>
        <input className="desk-input" type="number" min={0} inputMode="numeric" value={draft.limits[key]}
          onChange={event => set("limits", { ...draft.limits, [key]: event.target.value })} />
      </Field>)}
    </fieldset>
    <Field label="Allowed modules" hint="Module keys separated by commas. Empty allows every module.">
      <input className="desk-input" value={draft.modules} onChange={event => set("modules", event.target.value)} />
    </Field>
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={draft.is_active} onChange={event => set("is_active", event.target.checked)} />Offered for new assignments
    </label>
    {save.error ? <p role="alert" className="text-sm text-danger">{actionErrorText(save.error)}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button type="submit" className="desk-button-primary" disabled={!valid || save.isPending}>{save.isPending ? "Saving…" : plan ? "Save plan" : "Create plan"}</button>
      <button type="button" className="desk-button" onClick={onDone}>Cancel</button>
    </div>
  </form>;
}
