import type * as Api from "../../generated/api";
import { RouteLink } from "../../components/ui/RouteLink";

const PERIOD: Record<string, string> = { monthly: "per month", yearly: "per year" };

function cadence(plan: Api.PublicPlanCard) {
  if (plan.plan_type === "lifetime") return "once, for life";
  if (plan.plan_type === "financial_year") return "for the financial year";
  if (plan.plan_type === "fixed_end" && plan.fixed_end_date) return `until ${new Date(plan.fixed_end_date).toLocaleDateString()}`;
  return plan.interval === "custom_days" ? `every ${plan.custom_days ?? "?"} days` : PERIOD[plan.interval] ?? "";
}

/** X5: the space's listed membership plans with prices and a way to join. */
export function PublicPlanCards({ rows, slug }: { rows: Api.PublicPlanCard[]; slug?: string }) {
  return <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{rows.map((plan) => <li key={plan.id}
    className="grid content-start gap-2 rounded-xl border border-line bg-panel p-4">
    <h3 className="title-section">{plan.name}</h3>
    <p className="text-2xl font-semibold tabular-nums">{plan.amount} {plan.currency.toUpperCase()}
      <span className="ml-1 text-sm font-normal text-muted">{cadence(plan)}</span></p>
    {plan.description ? <p className="whitespace-pre-wrap text-sm text-muted">{plan.description}</p> : null}
    {plan.joining_fee ? <p className="text-sm text-muted">Joining fee {plan.joining_fee} {plan.currency.toUpperCase()}</p> : null}
    {slug && plan.join_mode !== "closed" ? <RouteLink className="desk-button justify-self-start" href={`/m/${slug}/member`}>
      {plan.join_mode === "open" ? "Join" : "Apply"}</RouteLink> : null}
  </li>)}</ul>;
}
