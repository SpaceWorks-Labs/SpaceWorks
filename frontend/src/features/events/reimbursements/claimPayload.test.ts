import { describe, expect, it } from "vitest";
import { claimDraftLines } from "./claimPayload";
import type { ClaimLine } from "./types";
const line: ClaimLine = { line_uuid: "line", category: "rail", original_amount_minor: 125000, original_currency: "INR",
  vendor: "Rail", traveller: "Maker", description: "Travel", expense_date: "2026-12-01", rate_date: "2026-12-01", rate_source: "receipt", fx_rate: "1", source_note: "", route: {},
  receipt: { asset_id: 91, generation: 1, sha256: "a".repeat(64), receipt_total_minor: 175000 } };
describe("claim draft boundary", () => {
  it("refuses unfinished receipts, fractional amounts, invalid FX and duplicate line identities", () => {
    for (const changed of [{ receipt: null }, { original_amount_minor: 1.5 }, { fx_rate: "0" }, { receipt: { ...line.receipt!, receipt_total_minor: 100 } }]) expect(() => claimDraftLines([{ ...line, ...changed }])).toThrow();
    expect(() => claimDraftLines([line, line])).toThrow(/distinct/);
  });
  it("drops inactive lodging columns after switching back to a travel expense", () => {
    expect(claimDraftLines([{ ...line, lodging_starts_on: "2026-12-01", lodging_ends_on: "2026-12-02", lodging_nights: 1 }])).toEqual([line]);
    expect(() => claimDraftLines([{ ...line, category: "lodging" }])).toThrow(/lodging/);
  });
});
