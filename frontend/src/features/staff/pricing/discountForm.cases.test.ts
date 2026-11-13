import { describe, expect, it } from "vitest";
import { describeDiscount, EMPTY_DISCOUNT, toBody, toForm, toLocalInput, validateDiscount, type DiscountForm } from "./discountForm";
import type { PriceDiscount } from "./pricingApi";

const form = (over: Partial<DiscountForm> = {}): DiscountForm => ({ ...EMPTY_DISCOUNT, name: "Spring", value: "10", ...over });
const rule = (over: Partial<PriceDiscount> = {}): PriceDiscount => ({ id: 1, name: "R", audience: "all_members", percent_bps: 1250, amount_off: null, ...over } as PriceDiscount);

describe("toLocalInput", () => {
  it.each([[null], [undefined], [""]])("is blank for %j", (iso) => expect(toLocalInput(iso)).toBe(""));
  it("renders local wall-clock time as YYYY-MM-DDTHH:mm with zero padding", () => {
    const d = new Date(2026, 0, 5, 7, 3);
    expect(toLocalInput(d.toISOString())).toBe("2026-01-05T07:03");
  });
});

describe("toForm", () => {
  it("reads a percentage rule from basis points", () => expect(toForm(rule({ percent_bps: 1250 }))).toMatchObject({ kind: "percent", value: "12.5", plan: null, member: null, domains: [], components: [], is_active: true }));
  it("reads a zero-percent rule as a percentage, not an amount", () => expect(toForm(rule({ percent_bps: 0 }))).toMatchObject({ kind: "percent", value: "0" }));
  it("reads an amount rule", () => expect(toForm(rule({ percent_bps: null, amount_off: "5.000" }))).toMatchObject({ kind: "amount", value: "5.000" }));
  it("reads an amount rule with no amount as blank", () => expect(toForm(rule({ percent_bps: null, amount_off: null })).value).toBe(""));
  it("keeps the plan, scope lists and active flag", () => expect(toForm(rule({ audience: "plan", plan: 4, domains: ["shop"], components: ["item"], is_active: false }))).toMatchObject({
    audience: "plan", plan: 4, domains: ["shop"], components: ["item"], is_active: false }));
  it("labels a member by name, falling back to 'Member <id>'", () => {
    expect(toForm(rule({ audience: "member", member: 9, member_name: "Ann" })).member).toEqual({ id: 9, label: "Ann" });
    expect(toForm(rule({ audience: "member", member: 9 })).member).toEqual({ id: 9, label: "Member 9" });
  });
});

describe("validateDiscount", () => {
  it("accepts a valid percentage discount", () => expect(validateDiscount(form())).toEqual({}));
  it("requires a name", () => expect(validateDiscount(form({ name: "  " }))).toEqual({ name: "Give the discount a name." }));
  it("requires a plan for plan audiences and a member for member audiences", () => {
    expect(validateDiscount(form({ audience: "plan" }))).toEqual({ plan: "Choose the plan whose members get this discount." });
    expect(validateDiscount(form({ audience: "member" }))).toEqual({ member: "Choose the member who gets this discount." });
    expect(validateDiscount(form({ audience: "plan", plan: 3 }))).toEqual({});
    expect(validateDiscount(form({ audience: "member", member: { id: 1, label: "A" } }))).toEqual({});
  });
  it.each(["", "0", "100.01", "abc", "10.123", "-5"])("refuses the percentage %j", (value) => expect(validateDiscount(form({ value }))).toEqual({ value: "Enter a percentage above 0 and up to 100." }));
  it.each(["0.01", "100", "33.33"])("accepts the percentage %s", (value) => expect(validateDiscount(form({ value }))).toEqual({}));
  it.each(["", "0", "0.000", "abc", "5.1234", "12345678901"])("refuses the amount %j", (value) => expect(validateDiscount(form({ kind: "amount", value }))).toEqual({
    value: "Enter an amount above 0, with no more decimals than the currency has." }));
  it.each(["1", "5.5", "5.123", "1234567890"])("accepts the amount %s", (value) => expect(validateDiscount(form({ kind: "amount", value }))).toEqual({}));
  it("requires the end to be after the start, and only when both are set", () => {
    expect(validateDiscount(form({ starts_at: "2026-05-02T10:00", ends_at: "2026-05-02T10:00" }))).toEqual({ ends_at: "The end must be after the start." });
    expect(validateDiscount(form({ starts_at: "2026-05-02T10:00", ends_at: "2026-05-01T10:00" }))).toEqual({ ends_at: "The end must be after the start." });
    expect(validateDiscount(form({ starts_at: "2026-05-01T10:00", ends_at: "2026-05-02T10:00" }))).toEqual({});
    expect(validateDiscount(form({ ends_at: "2026-05-01T10:00" }))).toEqual({});
  });
});

describe("toBody", () => {
  it("sends a percentage as rounded basis points and nulls the amount", () => expect(toBody(form({ value: " 12.5 ", name: " Spring " }))).toMatchObject({
    name: "Spring", audience: "all_members", percent_bps: 1250, amount_off: null, plan: null, member: null, starts_at: null, ends_at: null, is_active: true }));
  it("avoids float drift when converting to basis points", () => expect(toBody(form({ value: "33.33" })).percent_bps).toBe(3333));
  it("sends an amount as text and nulls the percentage", () => expect(toBody(form({ kind: "amount", value: " 5.50 " }))).toMatchObject({ percent_bps: null, amount_off: "5.50" }));
  it("sends the plan only for plan audiences and the member id only for member audiences", () => {
    expect(toBody(form({ audience: "plan", plan: 4, member: { id: 9, label: "x" } }))).toMatchObject({ plan: 4, member: null });
    expect(toBody(form({ audience: "member", plan: 4, member: { id: 9, label: "x" } }))).toMatchObject({ plan: null, member: 9 });
    expect(toBody(form({ audience: "member", member: null })).member).toBeNull();
  });
  it("converts local times to ISO instants", () => {
    const body = toBody(form({ starts_at: "2026-05-01T10:00", ends_at: "2026-05-02T10:00" }));
    expect(body.starts_at).toBe(new Date("2026-05-01T10:00").toISOString());
    expect(body.ends_at).toBe(new Date("2026-05-02T10:00").toISOString());
  });
});

describe("describeDiscount", () => {
  it("summarises percent, audience and area", () => expect(describeDiscount(rule(), "INR")).toBe("12.5% off · All members · Every area"));
  it("shows money for an amount discount, raw when there is no currency", () => {
    expect(describeDiscount(rule({ percent_bps: null, amount_off: "5.00" }), "")).toBe("5.00 off · All members · Every area");
    expect(describeDiscount(rule({ percent_bps: null, amount_off: "5.00" }), "INR")).toMatch(/^.*5.*off · All members · Every area$/);
    expect(describeDiscount(rule({ percent_bps: null, amount_off: null }), "")).toBe("0 off · All members · Every area");
  });
  it("names the audience: plan with and without a name, member with and without a name", () => {
    expect(describeDiscount(rule({ audience: "plan", plan_name: "Gold" }), "")).toContain("Members on Gold");
    expect(describeDiscount(rule({ audience: "plan" }), "")).toContain("Members on a plan");
    expect(describeDiscount(rule({ audience: "member", member_name: "Ann" }), "")).toContain("Ann");
    expect(describeDiscount(rule({ audience: "member" }), "")).toContain("One member");
  });
  it("prefers components over domains for the area, and joins several", () => {
    expect(describeDiscount(rule({ components: ["deposit", "damage"], domains: ["shop"] }), "")).toBe("12.5% off · All members · Refundable deposit, Damage");
    expect(describeDiscount(rule({ domains: ["shop"] }), "")).toBe("12.5% off · All members · Shop");
  });
});
