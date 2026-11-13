import { describe, expect, it } from "vitest";
import type { LendingDraft, LineDraft, PricingDraft } from "./pricingDraft";
import { billedMinutes, chargeStep, lineCents, toCents, workedExample } from "./pricingMath";

const line = (component: string, amount = "0", over: Partial<LineDraft> = {}): LineDraft => ({ component, amount, cap: "", grace_units: "", billing_increment: "", minimum: "", ...over });
const lending = (over: Partial<LendingDraft> = {}): LendingDraft => ({ deposit_mode: "none", deposit_amount: "", deposit_blocks_issue: false, late_per_day: "", late_cap: "", grace_days: "", ...over });
const draft = (lines: LineDraft[], over: Partial<PricingDraft> = {}): PricingDraft => ({ mode: "paid", lines, lending: null, ...over });
const USD = "USD";

describe("toCents", () => {
  it.each([["12", USD, 1200], ["12.5", USD, 1250], ["0.05", USD, 5], [" 7.00 ", USD, 700], ["1500", "JPY", 1500], ["1.234", "KWD", 1234], ["2.5", "KWD", 2500]])(
    "%j in %s is %i minor units", (value, currency, minor) => expect(toCents(value, currency)).toBe(minor));
  it.each([["12.345", USD], ["1.5", "JPY"], ["1.2345", "KWD"], ["", USD], ["abc", USD], ["-1", USD], [".5", USD], ["1.", USD], ["1,5", USD]])("refuses %j in %s", (value, currency) =>
    expect(toCents(value, currency)).toBeNull());
  it("is null for null and undefined, and defaults to two decimals", () => {
    expect(toCents(null)).toBeNull();
    expect(toCents(undefined)).toBeNull();
    expect(toCents("3.1")).toBe(310);
  });
});

describe("chargeStep", () => it.each([["KWD", 10], ["BHD", 10], ["USD", 1], ["JPY", 1]])("%s moves in steps of %i", (code, step) => expect(chargeStep(code)).toBe(step)));

describe("lineCents", () => {
  it("multiplies and rounds half-up to the step", () => {
    expect(lineCents(100, 3)).toBe(300);
    expect(lineCents(250, 1, 3)).toBe(83);
    expect(lineCents(1, 1, 2)).toBe(1);
    expect(lineCents(1, 1, 4)).toBe(0);
  });
  it("caps the raw amount before rounding, returning the cap itself", () => {
    expect(lineCents(100, 3, 1, 250)).toBe(250);
    expect(lineCents(100, 3, 1, 300)).toBe(300);
    expect(lineCents(100, 3, 1, 301)).toBe(300);
    expect(lineCents(100, 1, 1, null)).toBe(100);
    expect(lineCents(100, 1, 1, 0)).toBe(0);
  });
  it("rounds to the currency's charge step", () => {
    expect(lineCents(1234, 1, 1, null, 10)).toBe(1230);
    expect(lineCents(1235, 1, 1, null, 10)).toBe(1240);
  });
});

describe("billedMinutes", () => {
  it("bills nothing for a zero or negative job", () => { expect(billedMinutes(0, 15, 30)).toBe(0); expect(billedMinutes(-5, 15)).toBe(0); });
  it("rounds up to the increment", () => expect(billedMinutes(50, 15)).toBe(60));
  it("ignores an increment of one or less", () => { expect(billedMinutes(50, 1)).toBe(50); expect(billedMinutes(50, 0)).toBe(50); });
  it("never bills below the minimum", () => { expect(billedMinutes(10, 15, 30)).toBe(30); expect(billedMinutes(45, 15, 30)).toBe(45); });
});

describe("workedExample", () => {
  it("is null for a domain without an example", () => expect(workedExample("shop", draft([]), USD)).toBeNull());

  describe("loans", () => {
    it("says loans are free in free mode, still without deposit or late notes", () => expect(workedExample("loans", draft([], { mode: "free", lending: lending({ deposit_mode: "fixed", deposit_amount: "5", late_per_day: "1" }) }), USD))
      .toEqual({ lead: "Loans are free: a 3-day loan of 1 item costs nothing.", notes: [] }));
    it("adds the loan rental to three days of the daily rate", () => expect(workedExample("loans", draft([line("rental_per_loan", "2"), line("rental_per_day", "1.5")]), USD)!.lead)
      .toBe("A 3-day loan of 1 item costs $6.50 in rental."));
    it("applies the daily cap to the three-day amount", () => expect(workedExample("loans", draft([line("rental_per_day", "10", { cap: "12" })]), USD)!.lead)
      .toBe("A 3-day loan of 1 item costs $12.00 in rental."));
    it("treats a missing line as zero", () => expect(workedExample("loans", draft([]), USD)!.lead).toBe("A 3-day loan of 1 item costs $0.00 in rental."));
    it("notes a fixed deposit only when it is above zero", () => {
      expect(workedExample("loans", draft([], { lending: lending({ deposit_mode: "fixed", deposit_amount: "20" }) }), USD)!.notes).toEqual(["Plus a refundable deposit of $20.00 per loan."]);
      expect(workedExample("loans", draft([], { lending: lending({ deposit_mode: "fixed", deposit_amount: "0" }) }), USD)!.notes).toEqual([]);
    });
    it("notes per-product deposits", () => expect(workedExample("loans", draft([], { lending: lending({ deposit_mode: "per_product" }) }), USD)!.notes).toEqual(["Plus each item's own refundable deposit."]));
    it("notes late fees with the grace days, and the cap only when there is one", () => {
      expect(workedExample("loans", draft([], { lending: lending({ late_per_day: "2", grace_days: "1", late_cap: "10" }) }), USD)!.notes)
        .toEqual(["Each day late after 1 grace days adds $2.00, up to $10.00."]);
      expect(workedExample("loans", draft([], { lending: lending({ late_per_day: "2", grace_days: "x" }) }), USD)!.notes)
        .toEqual(["Each day late after 0 grace days adds $2.00."]);
    });
    it("says nothing about late fees when the daily fee is zero", () => expect(workedExample("loans", draft([], { lending: lending({ late_per_day: "0" }) }), USD)!.notes).toEqual([]));
  });

  describe("machines", () => {
    it("says machines are free in free mode", () => expect(workedExample("machines", draft([], { mode: "free" }), USD)).toEqual({ lead: "Machines are free: a 90-minute job costs nothing.", notes: [] }));
    it("prices 90 minutes by the hour plus the job fee", () => expect(workedExample("machines", draft([line("time", "60"), line("per_job", "5")]), USD)!.lead)
      .toBe("A 90-minute job costs $95.00."));
    it("adds 10 units of material when a material rate is set", () => expect(workedExample("machines", draft([line("time", "60"), line("material", "2")]), USD)!.lead)
      .toBe("A 90-minute job using 10 units of material costs $110.00."));
    it("explains billed minutes when the increment changes them", () => {
      const out = workedExample("machines", draft([line("time", "60", { billing_increment: "60" })]), USD)!;
      expect(out.lead).toBe("A 90-minute job costs $120.00.");
      expect(out.notes).toEqual(["Machine time is billed as 120 minutes."]);
    });
    it("explains a minimum, but not when the machine time is free", () => {
      expect(workedExample("machines", draft([line("time", "60", { minimum: "100" })]), USD)!.notes).toEqual(["Machine time is billed as 100 minutes."]);
      expect(workedExample("machines", draft([line("time", "0", { minimum: "100" })]), USD)!.notes).toEqual([]);
    });
  });

  describe("bookings", () => {
    it("says bookings are free in free mode", () => expect(workedExample("bookings", draft([], { mode: "free" }), USD)).toEqual({ lead: "Bookings are free: a 2-hour booking costs nothing.", notes: [] }));
    it("adds the booking fee to two hours", () => expect(workedExample("bookings", draft([line("per_booking", "3"), line("per_hour", "10")]), USD)!.lead).toBe("A 2-hour booking costs $23.00."));
    it("applies the hourly cap", () => expect(workedExample("bookings", draft([line("per_hour", "10", { cap: "15" })]), USD)!.lead).toBe("A 2-hour booking costs $15.00."));
    it("rounds billed time up to the increment", () => expect(workedExample("bookings", draft([line("per_hour", "10", { billing_increment: "180" })]), USD)!.lead).toBe("A 2-hour booking costs $30.00."));
  });

  describe("events", () => {
    const published = ["Published events keep their own price."];
    it("starts free in free mode or at a zero price", () => {
      expect(workedExample("events", draft([line("per_registration", "5")], { mode: "free" }), USD)).toEqual({ lead: "New events start free.", notes: published });
      expect(workedExample("events", draft([line("per_registration", "0")]), USD)!.lead).toBe("New events start free.");
    });
    it("shows the registration price otherwise", () => expect(workedExample("events", draft([line("per_registration", "5")]), USD)).toEqual({ lead: "New events start at $5.00 per registration.", notes: published }));
  });

  it("uses the currency's own exponent: yen have no cents, fils round to ten", () => {
    expect(workedExample("events", draft([line("per_registration", "500")]), "JPY")!.lead).toMatch(/500/);
    expect(workedExample("bookings", draft([line("per_hour", "1.005")]), "KWD")!.lead).toMatch(/2\.010/);
  });
});
