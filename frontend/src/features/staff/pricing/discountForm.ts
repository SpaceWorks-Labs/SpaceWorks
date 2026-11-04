import { formatMoney } from "../paymentsApi";
import { componentLabel, domainLabel, type PriceDiscount, type PricingDomain } from "./pricingApi";

export type DiscountForm = {
  name: string; audience: PriceDiscount["audience"]; plan: number | null; member: { id: number; label: string } | null;
  kind: "percent" | "amount"; value: string; domains: PricingDomain[]; components: string[];
  starts_at: string; ends_at: string; is_active: boolean;
};

export const EMPTY_DISCOUNT: DiscountForm = {
  name: "", audience: "all_members", plan: null, member: null, kind: "percent", value: "", domains: [], components: [],
  starts_at: "", ends_at: "", is_active: true,
};

/** ISO -> the `datetime-local` input's local `YYYY-MM-DDTHH:mm`. */
export function toLocalInput(iso: string | null | undefined) {
  if (!iso) return "";
  const date = new Date(iso);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function toForm(rule: PriceDiscount): DiscountForm {
  const percent = rule.percent_bps !== null && rule.percent_bps !== undefined;
  return {
    name: rule.name, audience: rule.audience, plan: rule.plan ?? null,
    member: rule.member ? { id: rule.member, label: rule.member_name ?? `Member ${rule.member}` } : null,
    kind: percent ? "percent" : "amount", value: percent ? String((rule.percent_bps ?? 0) / 100) : rule.amount_off ?? "",
    domains: rule.domains ?? [], components: rule.components ?? [], starts_at: toLocalInput(rule.starts_at),
    ends_at: toLocalInput(rule.ends_at), is_active: rule.is_active ?? true,
  };
}

export function validateDiscount(form: DiscountForm): Record<string, string> {
  const problems: Record<string, string> = {};
  if (!form.name.trim()) problems.name = "Give the discount a name.";
  if (form.audience === "plan" && !form.plan) problems.plan = "Choose the plan whose members get this discount.";
  if (form.audience === "member" && !form.member) problems.member = "Choose the member who gets this discount.";
  const value = form.value.trim();
  if (form.kind === "percent") {
    const percent = Number(value);
    if (!/^\d+(\.\d{1,2})?$/.test(value) || percent <= 0 || percent > 100) problems.value = "Enter a percentage above 0 and up to 100.";
  } else if (!/^\d{1,10}(\.\d{1,2})?$/.test(value) || Number(value) <= 0) {
    problems.value = "Enter an amount above 0, with at most two decimals.";
  }
  if (form.starts_at && form.ends_at && new Date(form.ends_at) <= new Date(form.starts_at)) {
    problems.ends_at = "The end must be after the start.";
  }
  return problems;
}

export function toBody(form: DiscountForm): Partial<PriceDiscount> {
  const value = form.value.trim();
  return {
    name: form.name.trim(), audience: form.audience,
    plan: form.audience === "plan" ? form.plan : null, member: form.audience === "member" ? form.member?.id ?? null : null,
    percent_bps: form.kind === "percent" ? Math.round(Number(value) * 100) : null,
    amount_off: form.kind === "amount" ? value : null,
    domains: form.domains, components: form.components,
    starts_at: form.starts_at ? new Date(form.starts_at).toISOString() : null,
    ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null,
    is_active: form.is_active,
  };
}

/** One-line summary for the list: how much, for whom, where. */
export function describeDiscount(rule: PriceDiscount, currency: string) {
  const amount = rule.percent_bps ? `${rule.percent_bps / 100}% off` : `${currency ? formatMoney(rule.amount_off ?? "0", currency) : rule.amount_off ?? "0"} off`;
  const who = rule.audience === "plan" ? `Members on ${rule.plan_name ?? "a plan"}`
    : rule.audience === "member" ? rule.member_name ?? "One member" : "All members";
  const where = rule.components?.length ? rule.components.map(componentLabel).join(", ")
    : rule.domains?.length ? rule.domains.map(domainLabel).join(", ") : "Every area";
  return `${amount} · ${who} · ${where}`;
}
