import { t } from "@lingui/core/macro";
import { SettingsQueryState } from "./SettingsQueryState";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CustomFormBuilder } from "../forms/CustomFormBuilder";
import { upgradeLegacyForm } from "../forms/upgradeLegacyForm";
import { admissionKeys, admissionSettings, saveAdmissionSettings, type AdmissionRecipe, type AdmissionSettings, type JoinMode, type PaymentTiming } from "../members/membershipAdmissionApi";
import { listPlans, membershipPlanKeys } from "./membershipPlansApi";
import { MembershipAdmissionExtras } from "./MembershipAdmissionExtras";
import { useStaffChargesOn } from "./useStaffChargesOn";
import { formatMoney } from "../../lib/money";

export const ADMISSION_RECIPES: [AdmissionRecipe, string][] = [
  ["free_open", "Free + open"], ["free_vouch", "Free + vouch"], ["paid_approval", "Paid + approval"], ["paid_invite_only", "Paid + invite-only"], ["closed", "Closed"],
];

export function admissionRecipeDraft(settings: AdmissionSettings, recipe: AdmissionRecipe): AdmissionSettings {
  const defaults = { ...settings, application_schema: null, vouches_required: 1, voucher_min_tenure_days: 30, voucher_pending_limit: 3, vouch_expiry_days: 30, vouch_replaces_approval: false };
  if (recipe === "closed") return { ...defaults, join_mode: "closed", default_plan: null, joining_fee: "0.00", payment_timing: "after_activation" };
  if (recipe === "free_open" || recipe === "free_vouch") return { ...defaults, join_mode: recipe === "free_open" ? "open" : "vouch", default_plan: null, joining_fee: "0.00", payment_timing: "after_activation" };
  return { ...defaults, join_mode: recipe === "paid_approval" ? "approval" : "invite_only", payment_timing: "before_activation" };
}

export function MembershipAdmissionSettings({ makerspaceId, features = [] }: { makerspaceId: number; features?: string[] }) {
  const client = useQueryClient();
  const settings = useQuery({ queryKey: admissionKeys.settings(makerspaceId), queryFn: () => admissionSettings(makerspaceId) });
  const plans = useQuery({ queryKey: membershipPlanKeys.plans(makerspaceId), queryFn: () => listPlans(makerspaceId) });
  const [draft, setDraft] = useState<AdmissionSettings | null>(null);
  const [recipe, setRecipe] = useState<AdmissionRecipe | "">("");
  // #184: with membership charges off there is no fee, payment timing or paid recipe to offer.
  const chargesOn = useStaffChargesOn("membership", makerspaceId);
  const value = draft ?? settings.data;
  const save = useMutation({ mutationFn: () => saveAdmissionSettings(makerspaceId, { ...value!, ...(recipe ? { recipe } : {}) }), onSuccess: (data) => {
    client.setQueryData(admissionKeys.settings(makerspaceId), data);
    setDraft(null); setRecipe("");
    void client.invalidateQueries({ queryKey: ["makerspace-settings", makerspaceId] });
    void client.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    void client.invalidateQueries({ queryKey: ["member"] });
    void client.invalidateQueries({ queryKey: ["walk-in-admission", makerspaceId] });
  } });
  if (settings.isPending) return <SettingsQueryState query={settings} resource={t`membership admission`} />;
  if (settings.isError || !value) return <SettingsQueryState query={settings} resource={t`membership admission`} />;
  const update = <K extends keyof AdmissionSettings>(key: K, next: AdmissionSettings[K]) => { setDraft({ ...value, [key]: next }); save.reset(); };
  const activePlans = plans.data?.filter((plan) => plan.is_active) ?? [];
  return <SettingsQueryState query={settings} resource={t`membership admission`}><SettingsRow label={t`Membership admission`} helper={t`Choose a recipe, then adjust its conditions. Saving updates current admission conditions. Submitted answers and raised charges keep their snapshots. Closed refuses every new joining path.`}><form className="@container grid min-w-0 gap-4 rounded-md border border-line bg-bg p-4" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
    <div></div>
    <fieldset disabled={save.isPending} className="grid gap-4">
      <div className="grid gap-3 @md:grid-cols-2">
        <label className="grid gap-1 text-sm text-ink">{t`Admission recipe`}<select className="desk-input max-w-full" value={recipe} onChange={(event) => {
          const next = event.target.value as AdmissionRecipe | "";
          setRecipe(next);
          if (next) setDraft(admissionRecipeDraft(value, next));
          save.reset();
        }}><option value="">{t`Custom settings`}</option>{ADMISSION_RECIPES.filter(([id]) => chargesOn || !id.startsWith("paid_")).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
        <label className="grid gap-1 text-sm text-ink">{t`Join mode`}<select className="desk-input max-w-full" value={value.join_mode} onChange={(event) => update("join_mode", event.target.value as JoinMode)}><option value="open">{t`Open`}</option><option value="approval">{t`Approval`}</option><option value="invite_only">{t`Invite-only`}</option><option value="vouch">{t`Vouch`}</option><option value="closed">{t`Closed`}</option></select></label>
        {chargesOn ? <label className="grid gap-1 text-sm text-ink">{t`Payment timing`}<select className="desk-input max-w-full" value={value.payment_timing} onChange={(event) => update("payment_timing", event.target.value as PaymentTiming)}><option value="after_activation">{t`Activate then charge`}</option><option value="before_activation">{t`Pay before activation`}</option></select></label> : null}
        <label className="grid gap-1 text-sm text-ink">{t`Default admission plan`}<select className="desk-input max-w-full" value={value.default_plan ?? ""} disabled={plans.isPending || plans.isError} onChange={(event) => update("default_plan", event.target.value ? Number(event.target.value) : null)}><option value="">{t`No default plan`}</option>{activePlans.map((plan) => <option key={plan.id} value={plan.id}>{plan.name}{chargesOn ? ` · ${formatMoney(plan.amount, plan.currency)}` : ""}</option>)}</select></label>
        {chargesOn ? <><label className="grid gap-1 text-sm text-ink">{t`Joining fee`}<input className="desk-input" type="number" required min="0" step="any" value={value.joining_fee} onChange={(event) => update("joining_fee", event.target.value)} /></label>
        <label className="grid gap-1 text-sm text-ink">{t`Joining fee currency`}<input className="desk-input" required pattern="[a-zA-Z]{3}" maxLength={3} value={value.joining_fee_currency} onChange={(event) => update("joining_fee_currency", event.target.value.toLowerCase())} /></label>
        <label className="grid gap-1 text-sm text-ink">{t`Re-join dues`}<select className="desk-input max-w-full" value={value.rejoin_dues_rule} onChange={(event) => { const rule = event.target.value as AdmissionSettings["rejoin_dues_rule"]; setDraft({ ...value, rejoin_dues_rule: rule, rejoin_after_days: rule === "after_lapse" ? value.rejoin_after_days ?? 365 : null }); save.reset(); }}><option value="once">{t`Once per person`}</option><option value="each_join">{t`On every re-join`}</option>{features.includes("membership.plan_rules") || ["never", "after_lapse"].includes(value.rejoin_dues_rule) ? <><option value="never">{t`Never`}</option><option value="after_lapse">{t`Again after a lapse`}</option></> : null}</select></label></> : null}
        <NumberField label={t`Application expiry (days)`} value={value.request_expiry_days} min={1} onChange={(next) => update("request_expiry_days", next)} />
      </div>
      <SettingsQueryState query={plans} resource={t`admission plans`} />
      {chargesOn ? null : <p className="text-sm text-muted">{t`Membership charges are off in this space, so membership is free.`}</p>}
      {chargesOn && recipe.startsWith("paid_") && !Number(value.joining_fee) && !activePlans.some((plan) => plan.id === value.default_plan && Number(plan.amount) > 0) ? <p className="text-sm text-warn-ink">{t`Choose a priced default plan or joining fee for this paid recipe.`}</p> : null}
      <fieldset className="grid gap-3 rounded border border-line p-3"><legend className="text-sm font-semibold text-ink">{t`Vouch rules`}</legend>
        <p className="text-sm text-muted">{t`Vouchers must be active, unrestricted members. Vouches record accountability without automatically restricting anyone.`}</p>
        <div className="grid gap-3 @md:grid-cols-2">
          <NumberField label={t`Vouches required`} min={1} value={value.vouches_required} onChange={(next) => update("vouches_required", next)} />
          <NumberField label={t`Minimum voucher tenure (days)`} min={0} value={value.voucher_min_tenure_days} onChange={(next) => update("voucher_min_tenure_days", next)} />
          <NumberField label={t`Pending applicants per voucher`} min={1} value={value.voucher_pending_limit} onChange={(next) => update("voucher_pending_limit", next)} />
          <NumberField label={t`Vouch expiry (days)`} min={1} value={value.vouch_expiry_days} onChange={(next) => update("vouch_expiry_days", next)} />
        </div>
        <label className="min-h-11 flex gap-2 text-sm text-ink"><input type="checkbox" checked={value.vouch_replaces_approval} onChange={(event) => update("vouch_replaces_approval", event.target.checked)} />{t`Vouches replace staff approval`}</label>
      </fieldset>
      <MembershipAdmissionExtras value={value} features={features} onChange={(next) => { setDraft(next); save.reset(); }} />
      <CustomFormBuilder value={value.application_schema} memberCard onChange={(schema) => update("application_schema", schema)} legend={t`Membership application questions`} emptyMessage={t`No application questions. Applicants submit their verified account identity.`} />
      {Array.isArray(value.application_schema) || !value.application_schema ? <div className="grid gap-1">
        {/* Parity O-F2: section headings, conditions and printable answers need the v2 form (the field holds either shape). */}
        <button className="desk-button justify-self-start" type="button" onClick={() => update("application_schema", upgradeLegacyForm(value.application_schema, `membership-join-${makerspaceId}`) as unknown as AdmissionSettings["application_schema"])}>{t`Switch to the new form builder`}</button>
        <p className="text-sm text-muted">{t`Adds section headings, show-if conditions and answers that can print on the member card. Applications already sent keep the answers they were made with.`}</p>
      </div> : null}
    </fieldset>
    <SettingsEditorActions dirty={Boolean(draft || recipe)} onDiscard={() => { setDraft(null); setRecipe(""); save.reset(); }} pending={save.isPending} disabled={save.isPending} />
    {save.isSuccess ? <p role="status" className="text-sm text-success-ink">{t`Admission settings saved.`}</p> : null}
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
  </form></SettingsRow></SettingsQueryState>;
}

function NumberField({ label, value, min, onChange }: { label: string; value: number; min: number; onChange: (value: number) => void }) {
  return <label className="grid gap-1 text-sm text-ink">{label}<input className="desk-input" type="number" required min={min} step="1" value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}
