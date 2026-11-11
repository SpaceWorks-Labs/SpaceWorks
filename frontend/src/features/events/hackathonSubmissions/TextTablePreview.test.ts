import { describe, expect, it } from "vitest";
import { parseTable, safeTableCsv } from "./TextTablePreview";

describe("inert maker tables", () => {
  it("handles quoted delimiters and line breaks", () => {
    expect(parseTable('Ref,Value\nR1,"a,b"\nR2,"line\nline"\n')).toEqual([
      ["Ref", "Value"], ["R1", "a,b"], ["R2", "line\nline"],
    ]);
  });
  it("escapes spreadsheet formulas and quotes only on generated export", () => {
    const rows = [["=2+2", " +SUM(A1)", "-1", "@cmd", 'a"b', "plain"]];
    expect(safeTableCsv(rows)).toBe('"\'=2+2","\' +SUM(A1)","\'-1","\'@cmd","a""b","plain"');
    expect(rows[0][0]).toBe("=2+2");
  });
  it("bounds cell length and refuses incomplete quotes", () => {
    expect(() => parseTable("Ref,Val\nR1,\"unfinished")).toThrow();
    expect(() => parseTable("Ref,Val\nR1," + "x".repeat(8193))).toThrow();
  });
});
