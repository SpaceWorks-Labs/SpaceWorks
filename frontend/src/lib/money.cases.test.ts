import { describe, expect, it } from "vitest";
import { currencyExponent, decimalToMinor, fixedMoney, formatMinorMoney, formatMoney, formatPrice, milliToMoney, minorToDecimal, moneyToMilli,
  paymentMethodLabel, percentOfMoney } from "./money";

describe("formatMoney edge inputs", () => {
  it("treats null, undefined and blank as zero", () => {
    for (const value of [null, undefined, "", 0]) expect(formatMoney(value, "USD")).toMatch(/0\.00/);
  });
  it("accepts a lowercase code and a numeric amount", () => expect(formatMoney(12.5, "usd")).toMatch(/12\.50/));
  it("falls back to 'amount CODE' for an invalid code, with two decimals", () => {
    expect(formatMoney("5", "??")).toBe("5.00 ??");
    expect(formatMoney(3, "")).toBe("3.00");
  });
  it("shows the raw text for a non-numeric amount under a bad code", () => expect(formatMoney("abc", "??")).toBe("abc ??"));
  it("keeps three decimals for a three-decimal currency and none for a zero-decimal one", () => {
    expect(formatMoney("1.5", "KWD")).toMatch(/1\.500/);
    expect(formatMoney("1500", "JPY")).toMatch(/1,500(?!\.)/);
  });
  it("keeps a negative amount negative", () => expect(formatMoney("-4", "USD")).toMatch(/-/));
});

describe("formatPrice", () => {
  it.each([[0], ["0"], ["0.000"], [null], [undefined]])("says Free for %j", (amount) => expect(formatPrice(amount, "USD")).toBe("Free"));
  it("shows a discount line as a negative amount, not Free", () => expect(formatPrice("-2", "USD")).toMatch(/-/));
  it("formats a paid amount", () => expect(formatPrice("9.5", "USD")).toMatch(/9\.50/));
});

describe("formatMinorMoney", () => {
  it.each([[null], [undefined], [1.5], [Number.MAX_SAFE_INTEGER + 2], [Number.NaN]])("is Unavailable for %j", (minor) => expect(formatMinorMoney(minor as never, "USD")).toBe("Unavailable"));
  it("places two-decimal digits exactly", () => {
    expect(formatMinorMoney(1250, "USD")).toMatch(/12\.50/);
    expect(formatMinorMoney(5, "USD")).toMatch(/0\.05/);
  });
  it("keeps a negative amount under a whole unit negative", () => {
    expect(formatMinorMoney(-5, "USD")).toMatch(/-.*0\.05|0\.05.*-/);
    expect(formatMinorMoney(-1250, "USD")).toMatch(/12\.50/);
  });
  it("does not round a very large ledger figure", () => expect(formatMinorMoney(9007199254740991, "USD")).toMatch(/90,071,992,547,409\.91/));
  it("uses no fraction for a zero-decimal currency and three for a three-decimal one", () => {
    expect(formatMinorMoney(1500, "JPY")).toMatch(/1,500(?!\.)/);
    expect(formatMinorMoney(1500, "KWD")).toMatch(/1\.500/);
  });
  it("falls back to decimal plus code for an unknown currency code", () => expect(formatMinorMoney(1250, "??")).toBe("12.50 ??"));
});

describe("currencyExponent", () => {
  it.each([["JPY", 0], ["jpy", 0], ["KWD", 3], ["USD", 2], ["", 2], ["XXX", 2]])("%s has %i decimals", (code, n) => expect(currencyExponent(code)).toBe(n));
  it("treats a missing code as two decimals", () => expect(currencyExponent(undefined as never)).toBe(2));
});

describe("fixedMoney", () => {
  it.each([[1, "1.00"], [1.5, "1.50"], [1.005, "1.005"], [0.1 + 0.2, "0.30"], [2.0004, "2.00"], [-1.25, "-1.25"], [0, "0.00"]])("%d reads %s", (value, text) => expect(fixedMoney(value)).toBe(text));
});

describe("minorToDecimal", () => {
  it.each([[null], [undefined], [0.5], [Number.POSITIVE_INFINITY]])("is blank for %j", (minor) => expect(minorToDecimal(minor as never, "USD")).toBe(""));
  it.each([[1250, "USD", "12.50"], [5, "USD", "0.05"], [-5, "USD", "-0.05"], [-1250, "USD", "-12.50"], [0, "USD", "0.00"], [1500, "JPY", "1500"],
    [-7, "JPY", "-7"], [1500, "KWD", "1.500"], [1, "KWD", "0.001"]])("%i %s reads %s", (minor, code, text) => expect(minorToDecimal(minor, code)).toBe(text));
});

describe("decimalToMinor", () => {
  it.each([["12.5", "USD", 1250], ["12", "USD", 1200], ["12.", "USD", 1200], ["-3", "USD", -300], ["-0.05", "USD", -5], [" 1200.00 ", "USD", 120000], ["0", "USD", 0],
    ["1500", "JPY", 1500], ["1.234", "KWD", 1234]])("%j in %s is %i minor units", (text, code, minor) => expect(decimalToMinor(text, code)).toBe(minor));
  it.each([["12.345", "USD"], ["1.5", "JPY"], ["abc", "USD"], ["", "USD"], ["1,5", "USD"], ["--1", "USD"], [".5", "USD"], ["1.2.3", "USD"], ["+3", "USD"]])("refuses %j in %s", (text, code) =>
    expect(decimalToMinor(text, code)).toBeNull());
  it("refuses an amount beyond a safe integer, in both directions", () => {
    expect(decimalToMinor("90071992547409.92", "USD")).toBeNull();
    expect(decimalToMinor("-90071992547409.92", "USD")).toBeNull();
    expect(decimalToMinor("90071992547409.91", "USD")).toBe(9007199254740991);
  });
});

describe("moneyToMilli and milliToMoney", () => {
  it.each([["12", 12000n], ["12.5", 12500n], ["12.505", 12505n], ["0.001", 1n], ["12.", 12000n], [" 3 ", 3000n]])("%j is %s thousandths", (text, milli) => expect(moneyToMilli(text)).toBe(milli));
  it.each(["", "-1", "1.2345", "abc", ".5", "1,5"])("refuses %j", (text) => expect(moneyToMilli(text)).toBeNull());
  it.each([[12500n, "12.500"], [1n, "0.001"], [0n, "0.000"], [123456789012345678n, "123456789012345.678"]])("%s thousandths reads %s", (milli, text) => expect(milliToMoney(milli)).toBe(text));
  it("round-trips exactly", () => expect(milliToMoney(moneyToMilli("12.34")!)).toBe("12.340"));
});

describe("percentOfMoney", () => {
  it.each([["100", "18", "INR", "18.00"], ["99.99", "18", "USD", "18.00"], ["0.10", "50", "USD", "0.05"], ["0.01", "50", "USD", "0.01"], ["0.01", "49", "USD", "0.00"],
    ["1000", "18", "JPY", "180"], ["999", "0.5", "JPY", "5"], ["1000", "18", "KWD", "180.000"], ["10", "12.3456", "USD", "1.23"], ["0", "10", "USD", "0.00"]])(
    "%s x %s%% in %s is %s", (amount, percent, code, expected) => expect(percentOfMoney(amount, percent, code)).toBe(expected));
  it.each([["abc", "10"], ["10", "abc"], ["-5", "10"], ["10", "-1"], ["10", "1.23456"], ["", "10"], ["10", ""]])("is null for amount %j and percent %j", (amount, percent) =>
    expect(percentOfMoney(amount, percent, "USD")).toBeNull());
});

describe("paymentMethodLabel", () => {
  it.each([["cash", "Cash"], ["upi", "UPI"], ["bank_transfer", "Bank transfer"], ["card", "Card"], ["card_machine", "Card machine"], ["cheque", "Cheque"],
    ["online", "Online"], ["paypal", "PayPal"], ["wise", "Wise"], ["other", "Other"], ["crypto_wallet", "crypto wallet"]])("%s reads %s", (method, label) => expect(paymentMethodLabel(method)).toBe(label));
});
