import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { FormPageLayout } from "../../../components/layouts";
import { Field, SegmentedControl } from "../../../components/ui";
import { DiscountAudienceFields } from "./DiscountAudienceFields";
import { DiscountScopeFields } from "./DiscountScopeFields";
import { EMPTY_DISCOUNT, toBody, toForm, validateDiscount, type DiscountForm } from "./discountForm";
import { pricingApi, pricingError, type PriceDiscount, type PricingDomain } from "./pricingApi";

export const DISCOUNT_RULES = "Only the single best automatic discount applies, then an event promo code. Deposits, late, "
  + "damage and lost fees are never discounted unless you name them.";

/** Create or change one member discount rule. */
export function DiscountEditor({ makerspaceId, rule, currency, domains, membershipOn, onDone }: {
  makerspaceId: number; rule: PriceDiscount | null; currency: string; domains: PricingDomain[]; membershipOn: boolean;
  onDone: () => void;
}) {
  const client = useQueryClient();
  const [form, setForm] = useState<DiscountForm>(() => (rule ? toForm(rule) : EMPTY_DISCOUNT));
  const [problems, setProblems] = useState<Record<string, string>>({});
  const save = useMutation({
    mutationFn: () => rule ? pricingApi.updateDiscount(makerspaceId, rule.id, toBody(form))
      : pricingApi.createDiscount(makerspaceId, toBody(form)),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ["pricing-discounts", makerspaceId] }); onDone(); },
  });
  const set = (patch: Partial<DiscountForm>) => {
    setForm(current => ({ ...current, ...patch }));
    setProblems(current => { const next = { ...current }; Object.keys(patch).forEach(key => delete next[key]); return next; });
  };
  const submit = () => {
    const next = validateDiscount(form);
    setProblems(next);
    if (!Object.keys(next).length) save.mutate();
  };
  return <FormPageLayout state={{ status: "ready" }} width="narrow"
    back={{ label: t`Back to discounts`, onClick: onDone }}
    header={{ title: rule ? t`Edit ${rule.name}` : t`New member discount`, subtitle: DISCOUNT_RULES, headingLevel: 2 }}
    submit={{ label: rule ? t`Save discount` : t`Create discount`, pending: save.isPending, pendingLabel: t`Saving…`, onClick: submit }}
    cancel={{ label: t`Cancel`, onClick: onDone }}
    form={<div className="grid gap-4">
      <Field label={t`Name`} hint={t`Members see this name on their receipt.`} error={problems.name}>
        <input className="desk-input" maxLength={80} value={form.name} onChange={event => set({ name: event.target.value })} />
      </Field>
      <DiscountAudienceFields makerspaceId={makerspaceId} form={form} problems={problems} membershipOn={membershipOn} onChange={set} />
      <div className="grid gap-2">
        <span className="text-sm font-semibold text-ink">{t`Discount`}</span>
        <SegmentedControl label={t`Discount kind`} value={form.kind} onChange={value => set({ kind: value as DiscountForm["kind"], value: "" })}
          options={[{ value: "percent", label: t`Percent off` }, { value: "amount", label: t`Fixed amount off` }]} />
        <Field label={form.kind === "percent" ? t`Percent off (%)` : currency ? t`Amount off (${currency.toUpperCase()})` : t`Amount off`} error={problems.value}
          hint={form.kind === "amount" ? t`Spread over the eligible prices, largest first. A price never goes below zero.` : undefined}>
          <input className="desk-input" inputMode="decimal" value={form.value} onChange={event => set({ value: event.target.value })} />
        </Field>
      </div>
      <DiscountScopeFields domains={domains} form={form} onChange={set} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t`Starts (optional)`}><input className="desk-input" type="datetime-local" value={form.starts_at}
          onChange={event => set({ starts_at: event.target.value })} /></Field>
        <Field label={t`Ends (optional)`} error={problems.ends_at}><input className="desk-input" type="datetime-local" value={form.ends_at}
          onChange={event => set({ ends_at: event.target.value })} /></Field>
      </div>
      <label className="flex min-h-11 items-center gap-3 text-sm">
        <input type="checkbox" className="h-4 w-4" checked={form.is_active} onChange={event => set({ is_active: event.target.checked })} />
        {t`Active: apply this discount to new charges`}</label>
      {save.error ? <p role="alert" className="text-sm text-danger">{pricingError(save.error)}</p> : null}
    </div>} />;
}
