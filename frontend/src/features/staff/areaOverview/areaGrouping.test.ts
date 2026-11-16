import { describe, expect, it } from "vitest";

import { allGroupKeys, areaChoices, areaOf, combine, filterAreas, groupLabel } from "./areaGrouping";
import type { AreaGroup } from "./areaOverviewApi";

const group = (overrides: Partial<AreaGroup>): AreaGroup => ({
  kind: "area", key: "area:machines", label: "machines", count: 0, attention: 0, money: [], finance: [], children: [], items: [],
  ...overrides,
});
const finance = (currency: string, values: Partial<Record<string, string>>) => ({
  currency, income: "0.00", other_income: "0.00", refunds: "0.00", expenses: "0.00", owed: "0.00", money_in: "0.00", ...values,
});

const laser = group({ kind: "machine_type", key: "machine_type:3", label: "Laser", count: 2,
  children: [group({ kind: "machine", key: "machine:7", label: "Laser A", count: 2 })] });
const machines = group({ count: 2, attention: 1, children: [laser, group({ kind: "machine_type", key: "machine_type:none", label: "" })],
  money: [{ currency: "", amount: "20.00" }], finance: [finance("inr", { expenses: "40.00", payouts: "5.00", net: "-45.00" })] });
const inventory = group({ key: "area:inventory", label: "inventory", count: 3, attention: 2,
  children: [group({ kind: "domain", key: "domain:loans", label: "loans" })],
  money: [{ currency: "", amount: "6.00" }], finance: [finance("inr", { income: "100.00", owed: "75.00", net: "100.00" }),
    finance("usd", { income: "10.00", net: "10.00" })] });

describe("area grouping (decision 241)", () => {
  it("words areas, the loans split and the 'not tied to one thing' groups; records keep their names", () => {
    expect(groupLabel(machines)).toBe("Machines");
    expect(groupLabel(inventory)).toBe("Inventory");
    expect(groupLabel(inventory.children[0])).toBe("Loans");
    expect(groupLabel(laser)).toBe("Laser");
    expect(groupLabel(machines.children[1])).toBe("No machine type");
    expect(groupLabel(group({ kind: "machine", key: "machine:none", label: "" }))).toBe("Not tied to one machine");
    expect(groupLabel(group({ kind: "category", key: "category:none", label: "" }))).toBe("No category");
  });

  it("filters to the chosen areas and keeps every area when nothing is chosen", () => {
    expect(filterAreas([machines, inventory], ["inventory"]).map(areaOf)).toEqual(["inventory"]);
    expect(filterAreas([machines, inventory], []).map(areaOf)).toEqual(["machines", "inventory"]);
    expect(areaChoices(["machines", "bookings"])).toEqual([{ value: "machines", label: "Machines" },
      { value: "bookings", label: "Bookings and rooms" }]);
  });

  it("adds up the visible groups per currency and never mixes currencies", () => {
    const all = combine([machines, inventory]);
    expect(all.count).toBe(5);
    expect(all.attention).toBe(3);
    expect(all.money).toEqual([{ currency: "", amount: "26.00" }]);
    expect(all.finance).toEqual([
      { currency: "inr", income: "100.00", other_income: "0.00", refunds: "0.00", expenses: "40.00", owed: "75.00",
        money_in: "0.00", payouts: "5.00", net: "55.00" },
      { currency: "usd", income: "10.00", other_income: "0.00", refunds: "0.00", expenses: "0.00", owed: "0.00",
        money_in: "0.00", net: "10.00" },
    ]);
    expect(combine(filterAreas([machines, inventory], ["machines"])).finance[0].expenses).toBe("40.00");
  });

  it("lists every nested group path for 'open all'", () => {
    expect(allGroupKeys([machines])).toEqual(["/area:machines", "/area:machines/machine_type:3",
      "/area:machines/machine_type:3/machine:7", "/area:machines/machine_type:none"]);
  });
});
