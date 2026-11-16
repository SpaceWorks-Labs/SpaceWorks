import { describe, expect, it } from "vitest";

import type { ShellItem, ShellSection } from "../../components/shell";
import { staffBottomNav } from "./staffBottomNav";

// Mutation-testing pins (decision 457): the bar is built from whatever the permission/module-filtered menu still offers.
const item = (key: string) => ({ key, label: key, to: `/${key}` }) as unknown as ShellItem;
const section = (keys: string[], more: string[] = []) =>
  ({ key: "s", label: "S", items: keys.map(item), more: more.length ? more.map(item) : undefined }) as unknown as ShellSection;
const keysOf = (nav: ShellSection[], mode: "space" | "platform" | null) => staffBottomNav(nav, mode)?.map(entry => entry.key);

describe("staffBottomNav candidate order and thresholds", () => {
  it("returns nothing without a mode, even when items exist", () => {
    expect(staffBottomNav([section(["dashboard", "schedule"])], null)).toBeUndefined();
  });

  it("falls back down the space list: bookings, events and payments are real candidates, in that order", () => {
    expect(keysOf([section(["bookings", "events"])], "space")).toEqual(["bookings", "events"]);
    expect(keysOf([section(["payments", "events"])], "space")).toEqual(["events", "payments"]);
    expect(keysOf([section(["payments", "bookings"])], "space")).toEqual(["bookings", "payments"]);
    expect(keysOf([section(["notifications", "bookings", "events", "payments", "requests"])], "space")).toEqual(["requests", "notifications", "bookings", "events"]);
  });

  it("needs at least two destinations: one is nothing, exactly two is a bar", () => {
    expect(staffBottomNav([section(["dashboard"])], "space")).toBeUndefined();
    expect(keysOf([section(["dashboard", "payments"])], "space")).toEqual(["dashboard", "payments"]);
    expect(staffBottomNav([section([])], "platform")).toBeUndefined();
    expect(keysOf([section(["platform-inbox", "platform-analytics"])], "platform")).toEqual(["platform-inbox", "platform-analytics"]);
  });

  it("keeps only four and reads the More overflow of every section", () => {
    expect(keysOf([section(["dashboard", "schedule"], ["requests", "notifications", "bookings"])], "space")).toEqual(["dashboard", "schedule", "requests", "notifications"]);
    expect(keysOf([section(["dashboard"]), section([], ["payments"])], "space")).toEqual(["dashboard", "payments"]);
  });

  it("never mixes the two lists", () => {
    expect(staffBottomNav([section(["dashboard", "schedule"])], "platform")).toBeUndefined();
    expect(staffBottomNav([section(["platform-dashboard", "platform-spaces"])], "space")).toBeUndefined();
  });
});
