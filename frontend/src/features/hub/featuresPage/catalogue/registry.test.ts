import { existsSync, readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { limitLabel } from "../../../staff/platformSpaces/limitCopy";
import { moduleKeys } from "../../../../lib/moduleLabels";
import { featureCatalogue } from "./index";
import { MODULE_LIMIT_KEYS } from "./limitData";
import { REGISTRY } from "./registryData";
import { reportTitle } from "./registryTitles";

// The backend registries are the source of truth: reports (operations/report_*), limits (makerspaces/limit_modules).
const apps = resolve(__dirname, "../../../../../../backend/apps");
const operations = resolve(apps, "operations");
const text = (file: string) => readFileSync(file, "utf8");

describe.skipIf(!existsSync(operations))("report catalogue mirrors the backend registry", () => {
  const sources = () => readdirSync(operations).filter(name => /^(report|reports|org_report)\w*\.py$/.test(name)).map(name => text(resolve(operations, name))).join("\n");

  it("names only reports that exist", () => {
    const all = sources();
    const keys = new Set(Object.values(REGISTRY).flatMap(row => row.reports));
    for (const key of keys) expect([key, all.includes(`"${key}"`)]).toEqual([key, true]);
  });

  it("lists on a module page every report the coverage table and the 0.12.0 definitions assign to it", () => {
    const expected: Record<string, Set<string>> = {};
    const add = (module: string, key: string) => { if (key !== "module-operational-health") (expected[module] ??= new Set()).add(key); };
    const coverage = text(resolve(operations, "report_coverage.py"));
    const pattern = /(?:"(\w+)": |REPORT_MODULE_COVERAGE\["(\w+)"\] = )ModuleReportCoverage\(\s*"\w+",\s*\(([^)]*)\)/g;
    for (const match of coverage.matchAll(pattern)) {
      for (const key of match[3].matchAll(/"([a-z0-9]+(?:-[a-z0-9]+)+)"/g)) add(match[1] ?? match[2], key[1]);
    }
    for (const match of text(resolve(operations, "report_definitions_r2_final.py")).matchAll(/_counts\("([\w-]+)",\s*"[\w.]+",\s*\(([^)]*)\)/g)) {
      for (const module of match[2].matchAll(/"(\w+)"/g)) add(module[1], match[1]);
    }
    const modules = new Set(moduleKeys() as string[]);
    for (const [module, keys] of Object.entries(expected)) {
      if (!modules.has(module)) continue;
      const have = new Set(featureCatalogue()[module as keyof ReturnType<typeof featureCatalogue>].reports.map(report => report.key));
      for (const key of keys) expect([module, key, have.has(key)]).toEqual([module, key, true]);
    }
    expect(Object.keys(expected).length).toBeGreaterThan(20);
  });

  it("uses the definitions' own titles where they are written out", () => {
    for (const match of text(resolve(operations, "report_definitions_r2_final.py")).matchAll(/_counts\("([\w-]+)"[\s\S]*?gettext_noop\("([^"]+)"\)\)/g)) {
      expect([match[1], reportTitle(match[1])]).toEqual([match[1], match[2]]);
    }
  });
});

describe.skipIf(!existsSync(resolve(apps, "makerspaces/limit_modules.py")))("limits mirror limit_modules.py", () => {
  const source = text(resolve(apps, "makerspaces/limit_modules.py"));
  const keyModule = source.slice(source.indexOf("KEY_MODULE = {"), source.indexOf("MODULE_EXEMPT = {"));
  const exempt = source.slice(source.indexOf("MODULE_EXEMPT = {"), source.indexOf("def module_of"));

  it("gives each module exactly the limit keys KEY_MODULE assigns it, under their human labels", () => {
    const backend: Record<string, string[]> = {};
    for (const match of keyModule.matchAll(/"(\w+)": "(\w+)"/g)) (backend[match[2]] ??= []).push(match[1]);
    expect(MODULE_LIMIT_KEYS).toEqual(backend);
    const catalogue = featureCatalogue();
    for (const module of moduleKeys()) {
      expect([module, catalogue[module].limits]).toEqual([module, (backend[module] ?? []).map(key => limitLabel(key))]);
    }
  });

  it("explains a module with no limit by its backend exemption, and only then", () => {
    const exempted = [...exempt.matchAll(/^\s+"(\w+)": gettext_noop/gm)].map(match => match[1]).sort();
    const without = moduleKeys().filter(module => !featureCatalogue()[module].limits.length).sort();
    expect(without).toEqual(exempted);
    for (const module of without) expect([module, Boolean(featureCatalogue()[module].noLimits)]).toEqual([module, true]);
    for (const module of moduleKeys().filter(key => !without.includes(key))) expect(featureCatalogue()[module].noLimits).toBeUndefined();
  });
});
