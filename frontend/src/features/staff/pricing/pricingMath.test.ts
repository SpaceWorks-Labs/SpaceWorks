import { describe, expect, it } from "vitest";

import type { PricingDefault } from "./pricingApi";
import { toDraft, toWrite, validateDraft } from "./pricingDraft";
import { billedMinutes, chargeStep, lineCents, toCents, workedExample } from "./pricingMath";

const line = (component: string, extra: Partial<PricingDefault["lines"][number]> = {}) => ({
  component, label: component, unit: "item", has_cap: false, has_grace: false, has_increment: false, has_minimum: false,
  discountable: true, staff_set: false, prefill_only: false, read_only: false, amount: "0.00", cap: null, grace_units: 0,
  billing_increment: 0, minimum: 0, source: "none", ...extra,
});
const card = (domain: PricingDefault["domain"], lines: PricingDefault["lines"], extra: Partial<PricingDefault> = {}): PricingDefault => ({
  domain, label: domain, enabled: true, currency: "usd", mode: "paid", stored: true, editable: true, via: "space_manager",
  locked: false, refusal: null, rental_timing: null, rental_timing_editable: false, failed_job_charge: null, lines, lending: null,
  ...extra,
});

describe("pricing math", () => {
  it("parses cents exactly and rounds half-up after the cap", () => {
    expect(toCents("12.3")).toBe(1230);
    expect(toCents("0.05")).toBe(5);
    expect(toCents("-1")).toBeNull();
    expect(toCents("1.234")).toBeNull();
    // 0.25 per hour x 90 minutes = 0.375 -> 0.38 (half-up)
    expect(lineCents(25, 90, 60)).toBe(38);
    // 5.00 x 3 days capped at 12.00 before rounding
    expect(lineCents(500, 3, 1, 1200)).toBe(1200);
    expect(lineCents(500, 3, 1, null)).toBe(1500);
  });

  it("bills minutes up to the increment and never below the minimum", () => {
    expect(billedMinutes(90, 60)).toBe(120);
    expect(billedMinutes(90, 0, 120)).toBe(120);
    expect(billedMinutes(0, 15, 30)).toBe(0);
  });

  it("builds a worked example per area from the unsaved form", () => {
    const loans = card("loans", [line("rental_per_loan", { amount: "2.00" }),
      line("rental_per_day", { unit: "item_day", has_cap: true, amount: "5.00", cap: "12.00" })], {
      lending: { deposit_mode: "fixed", deposit_amount: "20.00", deposit_blocks_issue: false, late_per_day: "1.00", late_cap: "0.00", grace_days: 2 },
    });
    const example = workedExample("loans", toDraft(loans), "usd")!;
    expect(example.lead).toBe("A 3-day loan of 1 item costs $14.00 in rental.");
    expect(example.notes).toEqual(["Plus a refundable deposit of $20.00 per loan.", "Each day late after 2 grace days adds $1.00."]);
    expect(workedExample("loans", { ...toDraft(loans), mode: "free" }, "usd")!.lead).toMatch(/costs nothing/);

    const machines = card("machines", [line("time", { unit: "hour", has_increment: true, has_minimum: true, amount: "10.00", billing_increment: 60 }),
      line("material", { amount: "0.00" }), line("per_job", { amount: "1.00" })]);
    expect(workedExample("machines", toDraft(machines), "usd")).toEqual({ lead: "A 90-minute job costs $21.00.",
      notes: ["Machine time is billed as 120 minutes."] });

    const bookings = card("bookings", [line("per_booking", { amount: "3.00" }),
      line("per_hour", { has_cap: true, has_increment: true, amount: "8.00", cap: "10.00" })]);
    expect(workedExample("bookings", toDraft(bookings), "usd")!.lead).toBe("A 2-hour booking costs $13.00.");
    expect(workedExample("membership", toDraft(card("membership", [])), "usd")).toBeNull();
  });

  it("validates and writes only the fields each line takes", () => {
    const data = card("bookings", [line("per_booking"), line("per_hour", { has_cap: true, has_increment: true }),
      line("dues", { read_only: true })]);
    const draft = toDraft(data);
    draft.lines[0].amount = "abc";
    draft.lines[1].billing_increment = "2000";
    expect(validateDraft(data, draft)).toEqual({ "line.per_booking.amount": expect.any(String),
      "line.per_hour.billing_increment": "Enter whole minutes from 0 to 1440." });
    draft.lines[0].amount = "4.5";
    draft.lines[1].billing_increment = "15";
    expect(toWrite(data, draft)).toEqual({ mode: "paid", lines: [{ component: "per_booking", amount: "4.5" },
      { component: "per_hour", amount: "0.00", cap: null, billing_increment: 15 }] });
  });
});

describe("currency exponents (F4)", () => {
  it("reads minor units in the currency's own exponent", () => {
    expect(toCents("12.5", "USD")).toBe(1250);
    expect(toCents("1500", "JPY")).toBe(1500);
    expect(toCents("1.5", "JPY")).toBeNull();
    expect(toCents("1.255", "KWD")).toBe(1255);
    expect(toCents("1.2555", "KWD")).toBeNull();
  });

  it("rounds a three-decimal charge once, to the 10-fils step the providers capture", () => {
    expect(chargeStep("KWD")).toBe(10);
    expect(chargeStep("USD")).toBe(1);
    // 3 hours at 0.125 KWD = 0.375 KWD -> 375 fils -> 380 on the 10-fils grid (half-up).
    expect(lineCents(125, 3, 1, null, chargeStep("KWD"))).toBe(380);
    expect(lineCents(125, 3, 1, null, 1)).toBe(375);
  });
});
