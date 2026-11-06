import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import type * as Api from "../../generated/api";
import { RouteLink } from "../../components/ui/RouteLink";
import { useChargesOn } from "../../lib/charges";

const PERIOD: Record<string, string> = { monthly: "per month", yearly: "per year" };

function cadence(plan: Api.PublicPlanCard) {
  if (plan.plan_type === "lifetime") return "once, for life";
  if (plan.plan_type === "financial_year") return "for the financial year";
  if (plan.plan_type === "fixed_end" && plan.fixed_end_date) return `until ${new Date(plan.fixed_end_date).toLocaleDateString(formatLocale())}`;
  return plan.interval === "custom_days" ? `every ${plan.custom_days ?? "?"} days` : PERIOD[plan.interval] ?? "";
}

/** X5: the space's listed membership plans with prices and a way to join. No price shows while membership charges are off (#184). */
export function PublicPlanCards({ rows, slug }: { rows: Api.PublicPlanCard[]; slug?: string }) {
  const showPrice = useChargesOn("membership", slug);
  return <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{rows.map((plan) => <li key={plan.id}
    className="grid content-start gap-2 rounded-xl border border-line bg-panel p-4">
    <h3 className="title-section">{plan.name}</h3>
    {showPrice ? <p className="text-2xl font-semibold tabular-nums">{plan.amount} {plan.currency.toUpperCase()}
      <span className="ml-1 text-sm font-normal text-muted">{cadence(plan)}</span></p> : null}
    {plan.description ? <p className="whitespace-pre-wrap text-sm text-muted">{plan.description}</p> : null}
    {showPrice && plan.joining_fee ? <p className="text-sm text-muted">{t`Joining fee ${plan.joining_fee} ${plan.currency.toUpperCase()}`}</p> : null}
    {slug && plan.join_mode !== "closed" ? <RouteLink className="desk-button justify-self-start" href={`/m/${slug}/member`}>
      {plan.join_mode === "open" ? t`Join` : t`Apply`}</RouteLink> : null}
  </li>)}</ul>;
}
