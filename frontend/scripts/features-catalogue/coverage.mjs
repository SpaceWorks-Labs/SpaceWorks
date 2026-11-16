// Evaluates backend/apps/operations/report_coverage.py WITHOUT Python: it reads the literal data and replays the
// statements that build REPORT_MODULE_COVERAGE, in file order. Any statement it does not recognise is returned in
// `unparsed`, so a new loop in that file makes `npm run features:catalogue -- --check` (and the freshness test) fail
// until this replay is taught about it.
import { readFileSync } from "node:fs";

const quoted = text => [...text.matchAll(/"([^"]+)"/g)].map(match => match[1]);
const uniq = list => [...new Set(list)];

export function evaluateCoverage(apps) {
  const source = readFileSync(`${apps}/operations/report_coverage.py`, "utf8");
  const head = source.slice(0, source.indexOf("@checks.register"));
  const contract = readFileSync(`${apps}/operations/report_coverage_contract.py`, "utf8");
  const repairs = uniq([...readFileSync(`${apps}/operations/report_definitions_repairs.py`, "utf8").matchAll(/_repairs\(\s*"([\w-]+)"/g)].map(match => match[1])).sort();
  const cov = new Map();
  const get = module => { if (!cov.has(module)) throw new Error(`coverage for ${module} used before it is defined`); return cov.get(module); };
  const append = (module, keys) => cov.set(module, uniq([...get(module), ...keys]));
  const steps = []; // { at, end, run }
  const claim = (match, run) => steps.push({ at: match.index, end: match.index + match[0].length, run });

  // 1. the literal table
  const open = head.indexOf("REPORT_MODULE_COVERAGE = {");
  const literalEnd = head.indexOf("\n}\n", open) + 3;
  for (const match of head.slice(open, literalEnd).matchAll(/"(\w+)": ModuleReportCoverage\("\w+", \(([^)]*)\)\)/g)) cov.set(match[1], quoted(match[2]));
  steps.push({ at: open, end: literalEnd, run: () => {} });

  // 2. replacements: ["m"] = ModuleReportCoverage("kind", ("a", "b"))  (first element is a string, no spread)
  for (const match of head.matchAll(/REPORT_MODULE_COVERAGE\["(\w+)"\] = ModuleReportCoverage\(\s*"\w+",\s*\(\s*("[^)]*)\),?\s*\)/g)) {
    claim(match, () => cov.set(match[1], quoted(match[2])));
  }
  // 3. appends that spread the module's own reports: ["m"] = ModuleReportCoverage(kind, (*REPORT_MODULE_COVERAGE["m"].reports, "k", ...))
  for (const match of head.matchAll(/REPORT_MODULE_COVERAGE\["(\w+)"\] = ModuleReportCoverage\(\s*[^,]+,\s*\(\s*\*REPORT_MODULE_COVERAGE\["\1"\]\.reports,([^)]*)\)\)/g)) {
    claim(match, () => append(match[1], quoted(match[2])));
  }
  // 4. the same inside .update({...})
  for (const match of head.matchAll(/"(\w+)": ModuleReportCoverage\("\w+", \(\*REPORT_MODULE_COVERAGE\["\1"\]\.reports,([^)]*)\)\)/g)) {
    if (match.index > literalEnd) claim(match, () => append(match[1], quoted(match[2])));
  }
  const update = /REPORT_MODULE_COVERAGE\.update\(\{[\s\S]*?\n\}\)/.exec(head);
  if (update) steps.push({ at: update.index, end: update.index + update[0].length, run: () => {} });
  // 5. the contract loop: every key of the acceptance table joins each module that table names
  const loop = /for _key, _modules in required_report_modules\(\)\.items\(\):[\s\S]*?\n\n/.exec(head);
  if (loop) claim(loop, () => {
    const byKey = new Map();
    for (const row of contract.matchAll(/\(\(([^()]*)\),\s*\(([^()]*)\)\)/g)) {
      for (const key of quoted(row[2])) byKey.set(key, uniq([...(byKey.get(key) ?? []), ...quoted(row[1])]));
    }
    for (const [key, modules] of byKey) for (const module of modules) append(module, [key]);
  });
  // 6. machine-area keys onto four modules
  const area = /_MACHINE_AREA_REPORT_KEYS = \(([^)]*)\)\s*for _module in \(([^)]*)\):[\s\S]*?\n\n/.exec(head);
  if (area) claim(area, () => { for (const module of quoted(area[2])) append(module, quoted(area[1])); });
  // 7. the repairs family
  const repairLoop = /for _module in \(("maintenance", "machines")\):[\s\S]*?sorted\(_REPAIRS_KEYS\)\)+\n/.exec(head);
  if (repairLoop) claim(repairLoop, () => { for (const module of quoted(repairLoop[1])) append(module, repairs); });
  // 8. inventory pairs: for _module, _keys in (("m", ("a",)), ...):
  const pairs = /for _module, _keys in \(([\s\S]*?)\):\n\s+REPORT_MODULE_COVERAGE\[_module\] = ModuleReportCoverage\(\s*REPORT_MODULE_COVERAGE\[_module\]\.kind, \(\*REPORT_MODULE_COVERAGE\[_module\]\.reports, \*_keys\)\)/.exec(head);
  if (pairs) claim(pairs, () => { for (const pair of pairs[1].matchAll(/\("(\w+)", \(([^)]*)\)\)/g)) append(pair[1], quoted(pair[2])); });
  // 9. release 0.12 loop: ("module", ("key",), "kind" | None)
  const release = /for _module, _keys, _kind in \(([\s\S]*?)\n\):\n[\s\S]*?\(\*_coverage\.reports, \*_keys\)\)\n/.exec(head);
  if (release) claim(release, () => { for (const row of release[1].matchAll(/\("(\w+)", \(([^)]*)\), (?:"\w+"|None)\)/g)) append(row[1], quoted(row[2])); });

  steps.sort((a, b) => a.at - b.at).forEach(step => step.run());
  // Anything that touches the table outside a recognised statement means this replay is out of date.
  const unparsed = [];
  for (const match of head.matchAll(/REPORT_MODULE_COVERAGE/g)) {
    if (!steps.some(step => match.index >= step.at && match.index < step.end) && !/^REPORT_MODULE_COVERAGE\s*=\s*\{/.test(head.slice(match.index, match.index + 30))) {
      unparsed.push(head.slice(match.index, head.indexOf("\n", match.index)).trim());
    }
  }
  return { coverage: Object.fromEntries(cov), unparsed };
}
