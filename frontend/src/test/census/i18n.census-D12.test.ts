import { relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import ts from "typescript";
// @ts-expect-error The production literal guard is a JavaScript module without declarations.
import { findUnmarked, proseLiterals, isMarked, isIgnored } from "../../../scripts/i18n-literal-positions.mjs";
// @ts-expect-error The production worker-closure enumerator is a JavaScript module without declarations.
import { workerClosure } from "../../../scripts/i18n-worker-closure.mjs";
import { ROOT, SRC, source, sourceFiles } from "./source.census-D12";
import { LITERAL_EXEMPTIONS } from "./exceptions.census-D12";
import { I18N_DEFECTS, SOURCE_EXEMPTIONS, DECLARATION_EXEMPTIONS } from "./literals.census-D12";

type Finding = { line: number; category: string };
const files = sourceFiles();
const posix = (file: string) => relative(SRC, file).split("\\").join("/");
const workers = new Set<string>([...workerClosure(ROOT) as Set<string>].map(posix));
// Keep repaired regressions named and enrolled as ordinary assertion parameters.
const REGRESSIONS: Record<string, { id: string; reason: string }> = {
  "features/inventory/PublicItemPage.tsx:title": { id: "CENSUS-D12-3",
    reason: "The item missing/module-off/detail titles must be Lingui-marked." },
  "features/inventory/PublicItemPage.tsx:description": { id: "CENSUS-D12-4",
    reason: "The public item metadata description must be Lingui-marked." },
};
function displayDeclarations(sf: ts.SourceFile) {
  const output: { key: string; findings: Finding[]; initializer: string; start: number; end: number }[] = [];
  const walk = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && /^(title|description|body|label|message|subtitle|heading)$/.test(node.name.getText()) && node.initializer) {
      const findings = (proseLiterals(node.initializer) as ts.Node[]).filter(literal =>
        !isMarked(literal) && !isIgnored(sf, literal)).map(literal => ({
          line: sf.getLineAndCharacterOfPosition(literal.getStart()).line + 1, category: "display variable",
        }));
      const key = `${posix(sf.fileName)}:${node.name.getText()}`;
      const initializer = node.initializer.getText();
      output.push({ key, initializer,
        start: sf.getLineAndCharacterOfPosition(node.getStart()).line + 1,
        end: sf.getLineAndCharacterOfPosition(node.end).line + 1,
        findings: DECLARATION_EXEMPTIONS[key]?.text === initializer ? [] : findings });
    }
    ts.forEachChild(node, walk);
  };
  walk(sf);
  return output;
}
const declarations = files.flatMap(file => displayDeclarations(source(file)));
function standardFindings(file: string): Finding[] {
  const sf = source(file);
  return (findUnmarked(sf) as Finding[]).filter(finding => {
    const exception = SOURCE_EXEMPTIONS[`${posix(file)}:${finding.line}`];
    return !exception || exception.text !== sf.text.split(/\r?\n/)[finding.line - 1];
  });
}
function declarationDefect(row: typeof declarations[number]) {
  const defect = I18N_DEFECTS[row.key];
  return defect?.findings.every(finding => finding.line >= row.start && finding.line <= row.end) ? defect : undefined;
}

describe("D12 Lingui census over the entire production source tree", () => {
  it("pins each reviewed non-display exception to its exact source contract", () => {
    for (const [key, entry] of Object.entries(SOURCE_EXEMPTIONS)) {
      const split = key.lastIndexOf(":");
      const sf = source(resolve(SRC, key.slice(0, split)));
      expect(sf.text.split(/\r?\n/)[Number(key.slice(split + 1)) - 1], key).toBe(entry.text);
      expect(entry.reason.trim(), key).not.toBe("");
    }
    for (const [key, entry] of Object.entries(DECLARATION_EXEMPTIONS)) {
      expect(declarations.filter(row => row.key === key && row.initializer === entry.text), key).toHaveLength(1);
      expect(entry.reason.trim(), key).not.toBe("");
    }
  });
  it("keeps new findings outside each strict expected-failure boundary", () => {
    for (const [key, defect] of Object.entries(I18N_DEFECTS)) {
      const rows = declarations.filter(row => row.key === key && declarationDefect(row) === defect);
      if (key === defect.file) expect(standardFindings(resolve(SRC, key)), key).toEqual(defect.findings);
      else {
        expect(rows, key).toHaveLength(1);
        expect(rows[0].findings, key).toEqual(defect.findings);
      }
    }
  });
  it("requires every literal exception, including newly added ignore comments, to have its frozen reason", () => {
    const actual: Record<string, string> = {};
    for (const file of files) source(file).text.split(/\r?\n/).forEach((line, index) => {
      if (line.includes("i18n-ignore:")) actual[`${posix(file)}:${index + 1}`] = line.split("i18n-ignore:")[1].trim();
    });
    expect(actual).toEqual(LITERAL_EXEMPTIONS);
    for (const reason of Object.values(actual)) expect(reason.trim()).not.toBe("");
  });
  it("scans worker-bundled files too and preserves the prohibition on Lingui macros there", () => {
    for (const worker of workers) {
      // generated/locales.ts (reached through lib/i18n.ts) is generator output, outside the
      // authored-source set by construction; it is still held to the macro prohibition below.
      if (worker !== "generated/locales.ts") expect(files.map(posix)).toContain(worker);
      const imports = source(resolve(SRC, worker)).statements.filter(ts.isImportDeclaration)
        .map(node => node.moduleSpecifier.getText());
      expect(imports.filter(name => /@lingui\/.*\/macro/.test(name))).toEqual([]);
    }
  });
  it("keeps each known display-literal regression attached to exactly one live declaration", () => {
    for (const key of Object.keys(REGRESSIONS)) expect(declarations.filter(row => row.key === key)).toHaveLength(1);
  });
  for (const file of files) {
    const name = posix(file), defect = I18N_DEFECTS[name];
    it(`marks every standard user-facing position in ${name}${defect ? ` | ${defect.id}` : ""}`, () => {
      expect(standardFindings(file)).toEqual([]);
    });
  }
  for (const row of declarations) {
    const regression = REGRESSIONS[row.key];
    const defect = declarationDefect(row);
    it(`${row.key}:${row.start}${defect ? ` | ${defect.id}` : ""}${regression ? ` | ${regression.id}: ${regression.reason}` : ""}`, () => {
      expect(row.findings).toEqual([]);
    });
  }
  it("keeps the item metadata source inside the census", () => {
    expect(files.includes(resolve(SRC, "features/inventory/PublicItemPage.tsx"))).toBe(true);
  });
});
