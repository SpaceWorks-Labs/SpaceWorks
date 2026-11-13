import { beforeEach, describe, expect, it, vi } from "vitest";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest }));

import { fields, hasQrConflicts, labelFor, mapRow, messageFor, parseDelimited, parseFileSample, suggestMapping } from "./BulkImportHelpers";

beforeEach(() => staffRequest.mockReset());

describe("parseDelimited", () => {
  it("returns no rows for empty or header-only input", () => {
    expect(parseDelimited("")).toEqual([]);
    expect(parseDelimited("name,qty\n")).toEqual([]);
  });
  it("keys each row by the trimmed header and pads missing cells with an empty string", () => expect(parseDelimited(" name , qty \nDrill,3\nSaw")).toEqual([
    { name: "Drill", qty: "3" }, { name: "Saw", qty: "" }]));
  it("detects tab separation when the text contains a tab", () => expect(parseDelimited("name\tqty\nDrill, 20V\t3")).toEqual([{ name: "Drill, 20V", qty: "3" }]));
  it("honours a forced delimiter", () => expect(parseDelimited("a;b\n1;2", ";")).toEqual([{ a: "1", b: "2" }]));
  it("keeps delimiters and newlines inside quotes and unescapes doubled quotes", () => expect(parseDelimited('name,note\n"Drill, big","line1\nline2 ""x"""')).toEqual([
    { name: "Drill, big", note: 'line1\nline2 "x"' }]));
  it("accepts CRLF and bare CR line endings", () => {
    expect(parseDelimited("a,b\r\n1,2\r\n3,4")).toEqual([{ a: "1", b: "2" }, { a: "3", b: "4" }]);
    expect(parseDelimited("a,b\r1,2")).toEqual([{ a: "1", b: "2" }]);
  });
  it("drops fully blank lines", () => expect(parseDelimited("a,b\n\n , \n1,2\n")).toEqual([{ a: "1", b: "2" }]));
});

describe("parseFileSample", () => {
  it("parses a CSV file", async () => expect(await parseFileSample(new File(["name,qty\nDrill,3"], "items.csv"), 1)).toEqual([{ name: "Drill", qty: "3" }]));
  it("parses a TSV file by extension even when the text has no tab in the sample", async () => expect(await parseFileSample(new File(["name,qty\tx\nA,1\t2"], "items.TSV"), 1)).toEqual([{ "name,qty": "A,1", x: "2" }]));
  it("reads only the first 256 KiB of a large file", async () => {
    const big = new File(["a,b\n" + "1,2\n".repeat(100_000)], "big.csv");
    const rows = await parseFileSample(big, 1);
    expect(rows.length).toBeGreaterThan(1000);
    expect(rows.length).toBeLessThan(100_000);
  });
  it("sends a workbook to the server for reading and returns its rows", async () => {
    staffRequest.mockResolvedValue({ rows: [{ name: "Drill" }] });
    const file = new File(["x"], "Items.XLSX");
    expect(await parseFileSample(file, 7)).toEqual([{ name: "Drill" }]);
    const [path, init] = staffRequest.mock.calls[0];
    expect(path).toBe("/admin/makerspace/7/inventory/import/sheet");
    expect(init.method).toBe("POST");
    expect((init.body as FormData).get("file")).toBeInstanceOf(File);
  });
});

describe("suggestMapping", () => {
  it("matches headers by field name or alias, ignoring case, underscores and spacing", () => expect(suggestMapping(["Item", "QTY", "In_Stock", "Shelf", "Notes", "Unknown"])).toEqual({
    name: "Item", total_quantity: "QTY", available_quantity: "In_Stock", storage_location: "Shelf", description: "Notes" }));
  it("uses the first header that matches a field", () => expect(suggestMapping(["product", "name"]).name).toBe("product"));
  it("omits fields with no matching header", () => expect(suggestMapping(["zzz"])).toEqual({}));
  it("recognises every field by its own key", () => expect(suggestMapping([...fields])).toEqual(Object.fromEntries(fields.map(f => [f, f]))));
});

describe("mapRow", () => {
  it("copies only mapped fields, using an empty string for a missing cell", () => expect(mapRow({ Item: "Drill", extra: "x" }, { name: "Item", category: "Cat" }))
    .toEqual({ name: "Drill", category: "" }));
  it("returns an empty object for an empty mapping", () => expect(mapRow({ a: 1 }, {})).toEqual({}));
});

describe("hasQrConflicts", () => {
  it("is true only when some error row mentions qr_code", () => {
    expect(hasQrConflicts({ errors: [{ row: 2, errors: { qr_code: "dup" } }] })).toBe(true);
    expect(hasQrConflicts({ errors: [{ row: 2, errors: { name: "required" } }] })).toBe(false);
    expect(hasQrConflicts({ errors: [] })).toBe(false);
    expect(hasQrConflicts({})).toBe(false);
    expect(hasQrConflicts(undefined)).toBe(false);
  });
});

describe("messages and labels", () => {
  it("joins row messages as 'key: value' separated by semicolons", () => expect(messageFor({ name: "required", qr_code: "taken" })).toBe("name: required; qr_code: taken"));
  it("gives an empty string for no messages", () => expect(messageFor({})).toBe(""));
  it("spells a field key with spaces", () => expect(labelFor("public_self_checkout_enabled")).toBe("public self checkout enabled"));
});
