import { t } from "@lingui/core/macro";
import { useState, type FormEvent } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "./ActionDialog";
import { limitHint } from "./limitCopy";
import { BYTE_LIMIT_KEYS, LIMIT_KEYS, limitLabels, useSavePlan, type HostingPlan, type LimitKey, type PlanBody } from "./plansApi";
import { currencyExponent, minorToDecimal } from "../../../lib/money";
import { moduleKeys, moduleLabel, moduleList } from "../../../lib/moduleLabels";
import { BoxArt } from "../../../components/BoxSpinner";

const MIB = 1024 * 1024;
type Draft = { key: string; name: string; description: string; is_active: boolean; trial_days: string; price: string; currency: string;
  billing_period: PlanBody["billing_period"]; modules: string[]; limits: Record<LimitKey, string> };

function draftOf(plan?: HostingPlan): Draft {
  const limits = Object.fromEntries(LIMIT_KEYS.map(key => {
    const value = plan?.limits[key];
    return [key, value === null || value === undefined ? "" : String(BYTE_LIMIT_KEYS.has(key) ? Math.round(value / MIB) : value)];
  })) as Record<LimitKey, string>;
  return { key: plan?.key ?? "", name: plan?.name ?? "", description: plan?.description ?? "", is_active: plan?.is_active ?? true,
    trial_days: String(plan?.trial_days ?? 0), price: plan ? minorToDecimal(plan.price_minor, plan.currency) : "0", currency: plan?.currency ?? "USD",
    billing_period: plan?.billing_period ?? "monthly", modules: [...(plan?.allowed_modules ?? [])], limits };
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
      return [key, text === "" ? null : BYTE_LIMIT_KEYS.has(key) ? Math.round(Number(text) * MIB) : Math.round(Number(text))];
    }));
    save.mutate({ key: draft.key, name: draft.name.trim(), description: draft.description.trim(), is_active: draft.is_active,
      trial_days: Math.round(Number(draft.trial_days)), price_minor: Math.round(Number(draft.price) * 10 ** currencyExponent(draft.currency)), currency: draft.currency.toUpperCase(),
      billing_period: draft.billing_period, limits, allowed_modules: draft.modules },
    { onSuccess: () => { toast(plan ? t`Plan saved.` : t`Plan created.`); onDone(); } });
  };
  return <form className="grid gap-4" aria-label={plan ? t`Edit ${plan.name}` : t`New plan`} onSubmit={submit} noValidate>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`Name`}><input className="desk-input" value={draft.name} onChange={event => set("name", event.target.value)} /></Field>
      <Field label={t`Short name`} hint={t`Used in links and exports: lowercase letters, numbers and hyphens, for example community-basic.`}><input className="desk-input" value={draft.key} autoCapitalize="none" onChange={event => set("key", event.target.value)} /></Field>
      <Field label={t`Price`} hint={t`What a space on this plan pays per billing period. 0 for free.`}><input className="desk-input" type="number" min={0} step="any" value={draft.price} onChange={event => set("price", event.target.value)} /></Field>
      <Field label={t`Currency`} hint={t`Three letters, for example USD or EUR.`}><input className="desk-input" maxLength={3} value={draft.currency} onChange={event => set("currency", event.target.value)} /></Field>
      <Field label={t`Billing period`} hint={t`How often an invoice is raised.`}>
        <select className="desk-input" value={draft.billing_period} onChange={event => set("billing_period", event.target.value as Draft["billing_period"])}>
          <option value="monthly">{t`Monthly`}</option><option value="yearly">{t`Yearly`}</option><option value="none">{t`No recurring bill`}</option>
        </select>
      </Field>
      <Field label={t`Trial days`} hint={t`Free days before the first invoice. 0 means no trial.`}><input className="desk-input" type="number" min={0} value={draft.trial_days} onChange={event => set("trial_days", event.target.value)} /></Field>
    </div>
    <Field label={t`Description`} hint={t`Shown to people choosing a plan.`}><textarea className="desk-input min-h-20" value={draft.description} onChange={event => set("description", event.target.value)} /></Field>
    <fieldset className="grid gap-3 sm:grid-cols-3">
      <legend className="mb-1 text-sm font-semibold text-ink">{t`Limits — leave a box empty for no limit`}</legend>
      {LIMIT_KEYS.map(key => <Field key={key} label={key === "storage" ? t`Storage (MB)` : key === "upload_bytes" ? t`Largest file (MB)` : limitLabels()[key]} hint={limitHint(key)}>
        <input className="desk-input" type="number" min={0} inputMode="numeric" placeholder={t`Unlimited`} value={draft.limits[key]}
          onChange={event => set("limits", { ...draft.limits, [key]: event.target.value })} />
      </Field>)}
    </fieldset>
    <ModulePicker value={draft.modules} onChange={modules => set("modules", modules)} />
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={draft.is_active} onChange={event => set("is_active", event.target.checked)} />{t`Available for new spaces (untick to retire the plan; spaces already on it keep it)`}</label>
    {save.error ? <p role="alert" className="text-sm text-danger">{actionErrorText(save.error)}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button type="submit" className="desk-button-primary" disabled={!valid || save.isPending}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : plan ? t`Save plan` : t`Create plan`}</button>
      <button type="button" className="desk-button" onClick={onDone}>{t`Cancel`}</button>
    </div>
  </form>;
}

/** The plan's allowed modules as translated checkboxes; nothing ticked means every feature. A key this
 * build no longer names (a retired module) stays listed, so saving never drops it silently. */
function ModulePicker({ value, onChange }: { value: string[]; onChange: (modules: string[]) => void }) {
  const options = [...new Set<string>([...moduleKeys(), ...value])].sort((a, b) => moduleLabel(a).localeCompare(moduleLabel(b)));
  const toggle = (key: string, checked: boolean) => onChange(checked ? [...value, key] : value.filter(item => item !== key));
  const included = moduleList(value);
  return <fieldset className="grid gap-2">
    <legend className="mb-1 text-sm font-semibold text-ink">{t`Features this plan includes`}</legend>
    <p className="text-sm text-muted">{value.length ? t`Included: ${included}. Core features are always included.` : t`Nothing ticked: every feature is included. Tick features to limit the plan to them.`}</p>
    <div className="grid gap-x-4 sm:grid-cols-2 lg:grid-cols-3">{options.map(key => <label key={key} className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={value.includes(key)} onChange={event => toggle(key, event.target.checked)} />{moduleLabel(key)}</label>)}</div>
  </fieldset>;
}
