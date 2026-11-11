import { describe, expect, it } from "vitest";

import { currencyExponent, decimalToMinor, formatMinorMoney, formatMoney, formatPrice, minorToDecimal } from "./money";

describe("money display", () => {
  it("formats an amount in its currency, case-insensitively", () => {
    expect(formatMoney("12.5", "eur")).toBe("€12.50");
    expect(formatMoney(1200, "INR")).toBe("₹1,200.00");
  });

  it("falls back to amount and code for a currency Intl cannot format", () => {
    expect(formatMoney("5", "")).toBe("5.00");
    expect(formatMoney("5", "not-a-code")).toBe("5.00 NOT-A-CODE");
  });

  it("calls nothing owed Free and keeps paid amounts", () => {
    expect(formatPrice("0.00", "usd")).toBe("Free");
    expect(formatPrice(null, "usd")).toBe("Free");
    expect(formatPrice("10", "usd")).toBe("$10.00");
  });
});

describe("decimal entry in minor units", () => {
  it("knows each currency's exponent", () => {
    expect(currencyExponent("eur")).toBe(2);
    expect(currencyExponent("JPY")).toBe(0);
    expect(currencyExponent("KWD")).toBe(3);
    expect(currencyExponent("not-a-code")).toBe(2);
  });

  // Final audit 0.12.0: CLDR says 0 digits for these; the server ledger keeps 2 (payments/money.py).
  it("follows the server's exponent where Intl disagrees, so typed amounts are not 100x off", () => {
    for (const code of ["IDR", "HUF", "COP", "AFN", "LAK"]) expect(currencyExponent(code), code).toBe(2);
    expect(decimalToMinor("150000", "IDR")).toBe(15000000);
    expect(minorToDecimal(15000000, "IDR")).toBe("150000.00");
    expect(formatMinorMoney(15000000, "IDR")).toMatch(/150,000\.00/);
    expect(formatMinorMoney(1234, "KWD")).toMatch(/1\.234/);
    expect(formatMinorMoney(1200, "JPY")).toMatch(/1,200/);
  });

  it("formatMoney keeps cents on a major IDR amount", () => {
    expect(formatMoney("1500.50", "IDR")).toMatch(/1,500\.50/);
  });

  it("parses a typed decimal exactly and refuses extra decimals", () => {
    expect(decimalToMinor("12.50", "EUR")).toBe(1250);
    expect(decimalToMinor("12.5", "EUR")).toBe(1250);
    expect(decimalToMinor("12.", "EUR")).toBe(1200);
    expect(decimalToMinor("-3", "EUR")).toBe(-300);
    expect(decimalToMinor("1.234", "KWD")).toBe(1234);
    expect(decimalToMinor("1200", "JPY")).toBe(1200);
    expect(decimalToMinor("12.5", "JPY")).toBeNull();
    expect(decimalToMinor("12.505", "EUR")).toBeNull();
    expect(decimalToMinor("1e2", "EUR")).toBeNull();
    expect(decimalToMinor("", "EUR")).toBeNull();
    expect(decimalToMinor("90071992547409.92", "EUR")).toBeNull();
  });

  it("shows stored minor units as the decimal a person would type", () => {
    expect(minorToDecimal(1250, "EUR")).toBe("12.50");
    expect(minorToDecimal(-5, "EUR")).toBe("-0.05");
    expect(minorToDecimal(1200, "JPY")).toBe("1200");
    expect(minorToDecimal(null, "EUR")).toBe("");
  });
});
