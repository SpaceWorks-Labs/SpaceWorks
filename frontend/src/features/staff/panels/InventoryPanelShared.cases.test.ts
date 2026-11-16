import { describe, expect, it } from "vitest";
import { adjustPayload, assetStatusLabel, defaultToBuyQuantity, emptyAdjust, emptyForm, formatActor, formatDate, formFromProduct, humanize,
  payloadFromForm, scanContextLabel, type AdminProduct } from "./InventoryPanelShared";

const product = (over: Partial<AdminProduct> = {}): AdminProduct => ({ id: 1, name: "Drill", tracking_mode: "quantity", category: 4, description: "d", total_quantity: 10,
  available_quantity: 7, reserved_quantity: 0, needs_fix_quantity: 0, storage_location: "A1", is_public: true, public_self_checkout_enabled: true, show_public_count: false,
  public_availability_mode: "exact_count", is_archived: false, ...over } as AdminProduct);

describe("payloadFromForm", () => {
  it("trims text identifiers, converts numbers and leaves optional keys out of a bare form", () => {
    const payload = payloadFromForm({ ...emptyForm, name: " Drill ", category: "4", manufacturer: " M ", model: " X ", sku: " S ", barcode: " B ", supplier: " Sup ", reorder_point: "3", reorder_quantity: "5" }, false);
    expect(payload).toMatchObject({ name: "Drill", category: 4, manufacturer: "M", model: "X", sku: "S", barcode: "B", supplier: "Sup", reorder_point: 3, reorder_quantity: 5 });
    for (const key of ["kit_components", "is_consumable", "public_show_expected_back", "event_only", "total_quantity", "available_quantity"]) expect(payload).not.toHaveProperty(key);
  });
  it("sends a missing category as null", () => expect(payloadFromForm(emptyForm, false).category).toBeNull());
  it("includes quantities only on request, treating blanks as 0", () => {
    expect(payloadFromForm({ ...emptyForm, total_quantity: "8", available_quantity: "5" }, true)).toMatchObject({ total_quantity: 8, available_quantity: 5 });
    expect(payloadFromForm({ ...emptyForm, total_quantity: "", available_quantity: "" }, true)).toMatchObject({ total_quantity: 0, available_quantity: 0 });
  });
  it("includes the lane L12 flags and kit components exactly when the form carries them, even when false or empty", () => {
    const payload = payloadFromForm({ ...emptyForm, is_consumable: false, public_show_expected_back: false, event_only: false, kit_components: [] }, false);
    expect(payload).toMatchObject({ is_consumable: false, public_show_expected_back: false, event_only: false, kit_components: [] });
  });
});

describe("adjustPayload", () => {
  it("converts deltas to numbers (blank is 0) and trims the reason", () => {
    expect(adjustPayload({ delta_available: "-2", delta_damaged: "", delta_lost: "1", reason: " broke " })).toEqual({ delta_available: -2, delta_damaged: 0, delta_lost: 1, reason: "broke" });
    expect(adjustPayload(emptyAdjust)).toEqual({ delta_available: 0, delta_damaged: 0, delta_lost: 0, reason: "" });
  });
});

describe("formFromProduct", () => {
  it("turns numbers into the text the inputs hold", () => expect(formFromProduct(product())).toMatchObject({ name: "Drill", category: "4", total_quantity: "10", available_quantity: "7",
    storage_location: "A1", reorder_point: "0", reorder_quantity: "0", manufacturer: "", borrowing_terms: "" }));
  it("uses blank text for a missing category or location", () => expect(formFromProduct(product({ category: null as never, storage_location: undefined as never }))).toMatchObject({ category: "", storage_location: "" }));
  it("copies master data and carries the lane L12 flags through unchanged", () => expect(formFromProduct(product({ manufacturer: "M", model: "X", sku: "S", barcode: "B", supplier: "Sup",
    reorder_point: 2, reorder_quantity: 6, borrowing_terms: "bt", is_consumable: true, public_show_expected_back: false, event_only: true }))).toMatchObject({
    manufacturer: "M", model: "X", sku: "S", barcode: "B", supplier: "Sup", reorder_point: "2", reorder_quantity: "6", borrowing_terms: "bt", is_consumable: true, public_show_expected_back: false, event_only: true }));
});

describe("defaultToBuyQuantity", () => {
  it.each([[10, 7, "1"], [10, 0, "3"], [100, 5, "16"], [0, 0, "1"], [5, 9, "1"]])("total %i with %i available suggests %s", (total, available, expected) =>
    expect(defaultToBuyQuantity(product({ total_quantity: total, available_quantity: available }))).toBe(expected));
});

describe("labels", () => {
  it("shows the role in brackets only when there is one", () => {
    expect(formatActor({ username: "ann", role: "staff" })).toBe("ann (staff)");
    expect(formatActor({ username: "ann", role: "" })).toBe("ann");
  });
  it("humanizes snake case and capitalises the first letter", () => expect(humanize("not_yet_done")).toBe("Not yet done"));
  it.each([["available", "Available"], ["reserved", "Reserved"], ["issued", "Issued"], ["damaged", "Damaged"], ["lost", "Lost"], ["retired", "Retired"],
    ["maintenance", "Maintenance"], ["archived", "Archived"], ["on_loan_elsewhere", "On loan elsewhere"]])("asset status %s reads %s", (s, l) => expect(assetStatusLabel(s)).toBe(l));
  it.each([["issue", "Issue"], ["return", "Return"], ["inventory_check", "Inventory check"], ["reassignment", "Reassignment"], ["scanner_lookup", "Scanner lookup"],
    ["member_lookup", "Member card lookup"], ["bulk_audit", "Bulk audit"]])("scan context %s reads %s", (s, l) => expect(scanContextLabel(s)).toBe(l));
  it("formats a valid date and returns an unparseable one untouched", () => {
    expect(formatDate("2026-05-01T10:00:00Z")).not.toBe("2026-05-01T10:00:00Z");
    expect(formatDate("not a date")).toBe("not a date");
  });
});
