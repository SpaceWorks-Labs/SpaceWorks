import { t } from "@lingui/core/macro";

import type { AreaFinance, AreaGroup, AreaMoney } from "./areaOverviewApi";
import { currencyExponent } from "../../../lib/money";

const FINANCE_SUMS = ["income", "other_income", "refunds", "expenses", "owed", "money_in", "payouts", "money_out", "net"] as const;

/** The area a top-level group stands for (`area:machines` -> `machines`). */
export function areaOf(group: AreaGroup) {
  return group.key.startsWith("area:") ? group.key.slice(5) : group.key;
}

function areaLabel(area: string) {
  const labels: Record<string, string> = {
    inventory: t`Inventory`, machines: t`Machines`, bookings: t`Bookings and rooms`, events: t`Events`,
    shop: t`Shop`, membership: t`Membership`, donations: t`Donations and sponsors`, general: t`General`,
  };
  return labels[area] ?? area;
}

function noneLabel(kind: string) {
  const labels: Record<string, string> = {
    machine_type: t`No machine type`, machine: t`Not tied to one machine`, category: t`No category`,
    room: t`No room`, event: t`Not tied to one event`,
  };
  return labels[kind] ?? t`Other`;
}

/** Plain words for a group heading: areas and the loans/inventory split are worded here, records keep their name. */
export function groupLabel(group: Pick<AreaGroup, "kind" | "key" | "label">) {
  if (group.kind === "area") return areaLabel(group.key.slice(5));
  if (group.kind === "domain") return group.key === "domain:loans" ? t`Loans` : t`Inventory`;
  if (group.key.endsWith(":none")) return noneLabel(group.kind);
  return group.label || noneLabel(group.kind);
}

export function areaChoices(areas: readonly string[]) {
  return areas.map(area => ({ value: area, label: areaLabel(area) }));
}

/** Keep only the chosen areas; an empty choice means every area the caller sees. */
export function filterAreas(groups: readonly AreaGroup[], chosen: readonly string[]) {
  return chosen.length ? groups.filter(group => chosen.includes(areaOf(group))) : [...groups];
}

/** Totals of the visible groups, so the summary line follows the area filter. */
export function combine(groups: readonly AreaGroup[]) {
  const money = new Map<string, number>();
  const finance = new Map<string, Record<string, number>>();
  let count = 0;
  let attention = 0;
  for (const group of groups) {
    count += group.count;
    attention += group.attention;
    for (const row of group.money) money.set(row.currency, (money.get(row.currency) ?? 0) + Number(row.amount));
    for (const row of group.finance) {
      const totals = finance.get(row.currency) ?? {};
      for (const name of FINANCE_SUMS) {
        const value = row[name];
        if (value !== undefined) totals[name] = (totals[name] ?? 0) + Number(value);
      }
      finance.set(row.currency, totals);
    }
  }
  return {
    count, attention,
    money: [...money.entries()].sort(([a], [b]) => a.localeCompare(b))
      .map(([currency, amount]): AreaMoney => ({ currency, amount: amount.toFixed(currencyExponent(currency)) })),
    finance: [...finance.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([currency, totals]) => ({
      currency, ...Object.fromEntries(Object.entries(totals).map(([name, value]) => [name, value.toFixed(currencyExponent(currency))])),
    }) as AreaFinance),
  };
}

/** Every group key in the tree, for "expand all". */
export function allGroupKeys(groups: readonly AreaGroup[], parent = ""): string[] {
  return groups.flatMap(group => {
    const path = `${parent}/${group.key}`;
    return [path, ...allGroupKeys(group.children, path)];
  });
}
