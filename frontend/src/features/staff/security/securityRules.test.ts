import { describe, expect, it } from "vitest";
import type { SecuritySetting } from "../../../lib/api/securitySettings";
import { asList, choiceLabel, describeFloor, describeValue, INT_RULES, strictnessProblem } from "./securityRules";

const setting = (over: Partial<SecuritySetting>): SecuritySetting => ({ key: "k", label: "L", description: "", kind: "int", default: 1, choices: [], value: 1, lock: null, ...over });
const locked = (floor: unknown) => ({ floor, note: "n", locked_at: "2026-01-01T00:00:00Z" });
const DAYS = "security.remembered_device_days";
const IDLE = "security.staff_idle_timeout_minutes";
const CHOICE = ["off", "after_failures", "always"];

describe("labels and lists", () => {
  it("names the three step-up choices and passes anything else through as text", () => {
    expect([choiceLabel("off"), choiceLabel("after_failures"), choiceLabel("always")]).toEqual(["Off", "After failed attempts", "Always"]);
    expect(choiceLabel("custom")).toBe("custom");
    expect(choiceLabel(5)).toBe("5");
  });
  it("turns a list value into strings and anything else into an empty list", () => {
    expect(asList([1, "a"])).toEqual(["1", "a"]);
    expect(asList("a")).toEqual([]);
    expect(asList(null)).toEqual([]);
  });
  it("defines the three bounded number rules", () => expect(INT_RULES).toEqual({
    [DAYS]: { min: 1, max: 90, unit: "days" }, "security.staff_session_max_hours": { min: 1, max: 720, unit: "hours" },
    [IDLE]: { min: 0, max: 1440, unit: "minutes", zeroOff: true } }));
});

describe("describeValue", () => {
  it("reads on/off switches", () => { expect(describeValue(setting({ kind: "bool" }), true)).toBe("On"); expect(describeValue(setting({ kind: "bool" }), false)).toBe("Off"); });
  it("reads a choice by its label", () => expect(describeValue(setting({ kind: "choice" }), "after_failures")).toBe("After failed attempts"));
  it("reads a network list by count, or as any network", () => {
    expect(describeValue(setting({ kind: "list" }), [])).toBe("Any network");
    expect(describeValue(setting({ kind: "list" }), ["10.0.0.0/8"])).toBe("1 network");
    expect(describeValue(setting({ kind: "list" }), ["a", "b"])).toBe("2 networks");
  });
  it("reads ranged numbers with their unit and the right plural", () => {
    expect(describeValue(setting({ key: DAYS }), 1)).toBe("1 day");
    expect(describeValue(setting({ key: DAYS }), 30)).toBe("30 days");
    expect(describeValue(setting({ key: "security.staff_session_max_hours" }), 1)).toBe("1 hour");
    expect(describeValue(setting({ key: "security.staff_session_max_hours" }), 8)).toBe("8 hours");
    expect(describeValue(setting({ key: IDLE }), 1)).toBe("1 minute");
    expect(describeValue(setting({ key: IDLE }), 15)).toBe("15 minutes");
  });
  it("reads zero as Off for a zero-off number only", () => {
    expect(describeValue(setting({ key: IDLE }), 0)).toBe("Off");
    expect(describeValue(setting({ key: DAYS }), 0)).toBe("0 days");
  });
  it("shows an unruled number as plain text", () => expect(describeValue(setting({ key: "other" }), 7)).toBe("7"));
});

describe("describeFloor", () => {
  it("describes a bool floor like a value", () => expect(describeFloor(setting({ kind: "bool" }), true)).toBe("On"));
  it("describes a choice floor as 'or stricter'", () => expect(describeFloor(setting({ kind: "choice" }), "after_failures")).toBe("After failed attempts or stricter"));
  it("describes a network floor, or any network when empty", () => {
    expect(describeFloor(setting({ kind: "list" }), ["10.0.0.0/8", "192.168.0.0/16"])).toBe("only networks within 10.0.0.0/8, 192.168.0.0/16");
    expect(describeFloor(setting({ kind: "list" }), [])).toBe("any network");
  });
  it("describes a number floor as 'at most', and a zero-off zero as any value", () => {
    expect(describeFloor(setting({ key: DAYS }), 30)).toBe("at most 30 days");
    expect(describeFloor(setting({ key: IDLE }), 0)).toBe("any value");
    expect(describeFloor(setting({ key: IDLE }), 30)).toBe("at most 30 minutes");
  });
});

describe("strictnessProblem for numbers", () => {
  const days = (lock: unknown = null) => setting({ key: DAYS, lock: lock === null ? null : locked(lock) });
  it.each([1.5, "abc", Number.NaN])("refuses %j as not a whole number", (value) => expect(strictnessProblem(days(), value)).toBe("Enter a whole number."));
  it("refuses a value outside the rule's range", () => {
    expect(strictnessProblem(days(), 0)).toBe("Choose 1–90 days.");
    expect(strictnessProblem(days(), 91)).toBe("Choose 1–90 days.");
    expect(strictnessProblem(days(), 1)).toBeNull();
    expect(strictnessProblem(days(), 90)).toBeNull();
  });
  it("accepts any whole number for an unruled setting without a lock", () => expect(strictnessProblem(setting({ key: "other" }), 5000)).toBeNull());
  it("enforces a platform lock floor as a ceiling", () => {
    expect(strictnessProblem(days(30), 30)).toBeNull();
    expect(strictnessProblem(days(30), 31)).toBe("The platform lock allows at most 30 days.");
  });
  it("lets a zero-off setting use anything when the lock is zero, but not zero when the lock is positive", () => {
    const idle = (floor: unknown) => setting({ key: IDLE, lock: locked(floor) });
    expect(strictnessProblem(idle(0), 600)).toBeNull();
    expect(strictnessProblem(idle(30), 0)).toBe("The platform lock allows at most 30 minutes.");
    expect(strictnessProblem(idle(30), 31)).toBe("The platform lock allows at most 30 minutes.");
    expect(strictnessProblem(idle(30), 10)).toBeNull();
  });
  it("ignores a lock whose floor is null or undefined", () => expect(strictnessProblem(setting({ key: DAYS, lock: locked(null) }), 80)).toBeNull());
});

describe("strictnessProblem for choices", () => {
  const choice = (floor?: unknown) => setting({ kind: "choice", choices: CHOICE, lock: floor === undefined ? null : locked(floor) });
  it("refuses a value that is not an option", () => expect(strictnessProblem(choice(), "never")).toBe("Choose one of the options."));
  it("accepts any option without a lock", () => expect(strictnessProblem(choice(), "off")).toBeNull());
  it("requires at least the locked strictness", () => {
    expect(strictnessProblem(choice("after_failures"), "off")).toBe("The platform lock allows After failed attempts or stricter.");
    expect(strictnessProblem(choice("after_failures"), "after_failures")).toBeNull();
    expect(strictnessProblem(choice("after_failures"), "always")).toBeNull();
    expect(strictnessProblem(choice("always"), "after_failures")).toBe("The platform lock allows Always or stricter.");
  });
  it("ignores a null floor", () => expect(strictnessProblem(choice(null), "off")).toBeNull());
});

describe("strictnessProblem for network lists", () => {
  const list = (floor?: unknown) => setting({ kind: "list", lock: floor === undefined ? null : locked(floor) });
  it("refuses an entry that is not a network", () => expect(strictnessProblem(list(), ["10.0.0.0/8", "nope"])).toBe("Each entry must be a network like 203.0.113.0/24 or 2001:db8::/32."));
  it("accepts any valid list, including empty, when there is no lock or an empty lock", () => {
    expect(strictnessProblem(list(), ["10.0.0.0/8"])).toBeNull();
    expect(strictnessProblem(list(), [])).toBeNull();
    expect(strictnessProblem(list([]), [])).toBeNull();
  });
  it("requires every entry to sit inside a locked network, and a non-empty list when locked", () => {
    const floor = ["10.0.0.0/8", "2001:db8::/32"];
    expect(strictnessProblem(list(floor), ["10.1.0.0/16", "2001:db8:1::/48"])).toBeNull();
    expect(strictnessProblem(list(floor), ["10.1.0.0/16", "11.0.0.0/8"])).toBe("The platform lock allows only networks within 10.0.0.0/8, 2001:db8::/32.");
    expect(strictnessProblem(list(floor), [])).toBe("The platform lock allows only networks within 10.0.0.0/8, 2001:db8::/32.");
    expect(strictnessProblem(list(floor), ["0.0.0.0/0"])).toBe("The platform lock allows only networks within 10.0.0.0/8, 2001:db8::/32.");
  });
});

describe("strictnessProblem for switches", () => it("never objects to an on/off value", () => expect(strictnessProblem(setting({ kind: "bool" }), true)).toBeNull()));
