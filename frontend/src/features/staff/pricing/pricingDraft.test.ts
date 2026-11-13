import { describe, expect, it } from "vitest";
import type { PricingDefault } from "./pricingApi";
import { toDraft, toWrite, validateDraft, type PricingDraft } from "./pricingDraft";

const spec = (component: string, over: Record<string, unknown> = {}) => ({ component, amount: "1.00", cap: null, grace_units: 0, billing_increment: 0, minimum: 0, ...over });
const card = (over: Record<string, unknown> = {}): PricingDefault => ({ mode: "paid", lines: [spec("rental_per_day", { has_cap: true, has_grace: true }), spec("time", { has_increment: true, has_minimum: true }),
  spec("locked", { read_only: true })], lending: null, ...over } as unknown as PricingDefault);
const MONEY_PROBLEM = "Enter an amount of 0 or more, with no more decimals than the currency has.";

describe("toDraft", () => {
  it("copies every number as the text the input holds, with defaults for missing values", () => {
    const draft = toDraft(card({ lines: [spec("a", { cap: undefined, grace_units: undefined, billing_increment: undefined, minimum: undefined }), spec("b", { cap: "9.00", grace_units: 2, billing_increment: 15, minimum: 30 })] }));
    expect(draft.lines).toEqual([{ component: "a", amount: "1.00", cap: "", grace_units: "0", billing_increment: "0", minimum: "0" },
      { component: "b", amount: "1.00", cap: "9.00", grace_units: "2", billing_increment: "15", minimum: "30" }]);
    expect(draft.mode).toBe("paid");
    expect(draft.lending).toBeNull();
  });
  it("copies lending with defaults, and coerces the blocking flag to a boolean", () => {
    expect(toDraft(card({ lending: {} })).lending).toEqual({ deposit_mode: "none", deposit_amount: "0.00", deposit_blocks_issue: false, late_per_day: "0.00", late_cap: "0.00", grace_days: "0" });
    expect(toDraft(card({ lending: { deposit_mode: "fixed", deposit_amount: "5.00", deposit_blocks_issue: 1, late_per_day: "1.00", late_cap: "9.00", grace_days: 3 } })).lending)
      .toEqual({ deposit_mode: "fixed", deposit_amount: "5.00", deposit_blocks_issue: true, late_per_day: "1.00", late_cap: "9.00", grace_days: "3" });
  });
});

describe("validateDraft", () => {
  const valid = (c = card()) => toDraft(c);
  it("accepts a valid card", () => expect(validateDraft(card(), valid())).toEqual({}));
  it("checks the amount for every editable line, and never a read-only or unknown line", () => {
    const draft = valid();
    draft.lines[0].amount = "abc"; draft.lines[2].amount = "abc";
    draft.lines.push({ component: "unknown", amount: "abc", cap: "", grace_units: "0", billing_increment: "0", minimum: "0" });
    expect(validateDraft(card(), draft)).toEqual({ "line.rental_per_day.amount": MONEY_PROBLEM });
  });
  it.each(["", "-1", "1.2345", "12345678901", "1,5", ".5"])("refuses the amount %j", (amount) => {
    const draft = valid(); draft.lines[0].amount = amount;
    expect(validateDraft(card(), draft)).toEqual({ "line.rental_per_day.amount": MONEY_PROBLEM });
  });
  it.each(["0", "0.5", "1234567890", "1.234"])("accepts the amount %s", (amount) => {
    const draft = valid(); draft.lines[0].amount = amount;
    expect(validateDraft(card(), draft)).toEqual({});
  });
  it("checks the cap only for lines that take one, and lets it be empty", () => {
    const draft = valid(); draft.lines[0].cap = "x"; draft.lines[1].cap = "x";
    expect(validateDraft(card(), draft)).toEqual({ "line.rental_per_day.cap": `${MONEY_PROBLEM} Leave empty for no cap.` });
    draft.lines[0].cap = "  ";
    expect(validateDraft(card(), draft)).toEqual({});
  });
  it("bounds grace days to 0-365, increments and minimums to 0-1440, and only where the line takes them", () => {
    const draft = valid();
    draft.lines[0].grace_units = "366"; draft.lines[1].billing_increment = "1441"; draft.lines[1].minimum = "-1";
    draft.lines[1].grace_units = "999"; draft.lines[0].billing_increment = "999";
    expect(validateDraft(card(), draft)).toEqual({
      "line.rental_per_day.grace_units": "Enter whole days from 0 to 365.",
      "line.time.billing_increment": "Enter whole minutes from 0 to 1440.",
      "line.time.minimum": "Enter whole minutes from 0 to 1440." });
    draft.lines[0].grace_units = "365"; draft.lines[1].billing_increment = "1440"; draft.lines[1].minimum = "0";
    expect(validateDraft(card(), draft)).toEqual({});
  });
  it("refuses a fractional or blank whole-number field", () => {
    const draft = valid(); draft.lines[0].grace_units = "1.5"; draft.lines[1].minimum = "";
    expect(Object.keys(validateDraft(card(), draft)).sort()).toEqual(["line.rental_per_day.grace_units", "line.time.minimum"]);
  });
  it("checks every lending amount and the grace days", () => {
    const withLending = card({ lines: [], lending: {} });
    const draft = toDraft(withLending);
    draft.lending!.deposit_amount = "x"; draft.lending!.late_per_day = "-1"; draft.lending!.late_cap = ""; draft.lending!.grace_days = "400";
    expect(validateDraft(withLending, draft)).toEqual({ "lending.deposit_amount": MONEY_PROBLEM, "lending.late_per_day": MONEY_PROBLEM, "lending.late_cap": MONEY_PROBLEM,
      "lending.grace_days": "Enter whole days from 0 to 365." });
    expect(validateDraft(withLending, toDraft(withLending))).toEqual({});
  });
});

describe("toWrite", () => {
  it("writes only the fields each line takes and never a read-only line", () => {
    const draft = toDraft(card({ lines: [spec("rental_per_day", { has_cap: true, has_grace: true, grace_units: 2, cap: "9.00" }), spec("time", { has_increment: true, has_minimum: true, billing_increment: 15, minimum: 30 }),
      spec("plain"), spec("locked", { read_only: true })] }));
    const sourceCard = card({ lines: [spec("rental_per_day", { has_cap: true, has_grace: true }), spec("time", { has_increment: true, has_minimum: true }), spec("plain"), spec("locked", { read_only: true })] });
    const write = toWrite(sourceCard, { ...draft, lines: draft.lines.map(l => ({ ...l, amount: ` ${l.amount} ` })) });
    expect(write.lines).toEqual([{ component: "rental_per_day", amount: "1.00", cap: "9.00", grace_units: 2 }, { component: "time", amount: "1.00", billing_increment: 15, minimum: 30 },
      { component: "plain", amount: "1.00" }]);
    expect(write).not.toHaveProperty("lending");
  });
  it("sends an empty cap as null so the cap is cleared", () => {
    const c = card({ lines: [spec("a", { has_cap: true })] });
    const draft = toDraft(c); draft.lines[0].cap = "  ";
    expect(toWrite(c, draft).lines[0]).toMatchObject({ cap: null });
  });
  it("skips draft lines the card does not know", () => {
    const c = card({ lines: [spec("a")] });
    const draft: PricingDraft = { mode: "paid", lines: [{ component: "ghost", amount: "1", cap: "", grace_units: "0", billing_increment: "0", minimum: "0" }], lending: null };
    expect(toWrite(c, draft).lines).toEqual([]);
  });
  it("writes the mode and trimmed lending with numeric grace days", () => {
    const c = card({ lines: [], lending: {} });
    const draft = toDraft(c);
    Object.assign(draft.lending!, { deposit_mode: "fixed", deposit_amount: " 5 ", deposit_blocks_issue: true, late_per_day: " 1 ", late_cap: " 9 ", grace_days: "3" });
    expect(toWrite(c, { ...draft, mode: "free" })).toEqual({ mode: "free", lines: [], lending: { deposit_mode: "fixed", deposit_amount: "5", deposit_blocks_issue: true,
      late_per_day: "1", late_cap: "9", grace_days: 3 } });
  });
});
