// Static documentation contracts: run with node --test; no Django or services required.
const assert = require("node:assert/strict");
const { readFileSync, existsSync } = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const test = require("node:test");

const root = path.resolve(__dirname, "../../..");
const read = (name) => readFileSync(path.join(root, name), "utf8");
const readme = read("README.md");

// Inspect literal catalogue declarations without importing Django or executing app code.
function declarations(file, constructor) {
  const result = spawnSync("python", ["-c", `
import ast, json, sys
tree = ast.parse(open(sys.argv[1], encoding="utf-8").read())
rows = []
for call in ast.walk(tree):
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
        continue
    if call.func.id != sys.argv[2]:
        continue
    args = [arg.value if isinstance(arg, ast.Constant) else None for arg in call.args]
    kwargs = {kw.arg: kw.value.value for kw in call.keywords if isinstance(kw.value, ast.Constant)}
    rows.append({"args": args, "kwargs": kwargs})
print(json.dumps(rows))
`, path.join(root, file), constructor], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  return JSON.parse(result.stdout);
}

test("orientation filenames remain byte-identical", () => {
  assert.deepEqual(readFileSync(path.join(root, "CLAUDE.md")),
    readFileSync(path.join(root, "AGENTS.md")));
});

test("README borrow-request matrix follows the pure access-policy resolver", () => {
  const result = spawnSync("python", ["-c", `
import json, runpy, sys
policy = runpy.run_path(sys.argv[1])
print(json.dumps([policy["policy_for"](modules, anonymous) for modules, anonymous in
                 [(["membership"], False), ([], False), ([], True), (["membership"], True)]]))
`, path.join(root, "backend/apps/makerspaces/request_access.py")], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  const modes = JSON.parse(result.stdout);
  const labels = { members: "Members", accounts: "Account holders", anyone: "Anyone" };
  const section = readme.split("| Membership (`membership`) | Account-less requests | Who may submit |")[1];
  assert.ok(section, "the matrix must name the membership module");
  const rows = [...section.split("\n\n")[0].matchAll(/^\| (on|off) \| (off|\*\*on\*\*) \| \*\*([^*]+)\*\*/gm)];
  assert.deepEqual(rows.map((row) => [row[1], row[2]]),
    [["on", "off"], ["off", "off"], ["off", "**on**"]]);
  assert.deepEqual(rows.map((row) => row[3]), modes.slice(0, 3).map((mode) => labels[mode]));
  assert.equal(modes[3], modes[0], "membership must override the anonymous flag");
});

test("README module inventory, core markers and defaults match the registry", () => {
  const definitions = declarations("backend/apps/makerspaces/module_registry_catalog.py", "ModuleDefinition");
  const rows = [...readme.matchAll(/^\|[^\n]*?\[`([^`]+)`\]\(docs\/MODULES\.md#([^)]*)\)\s*\|([^|]*)\|([^|]*)\|/gm)];
  assert.equal(rows.length, definitions.length, "each registry module needs exactly one table row");
  assert.equal(new Set(rows.map((row) => row[1])).size, rows.length, "duplicate module row");
  const byKey = new Map(rows.map((row) => [row[1], row]));
  const guide = read("docs/MODULES.md");
  for (const { args: [key], kwargs } of definitions) {
    const row = byKey.get(key);
    assert.ok(row, `missing ${key}`);
    assert.equal(row[2], key, `wrong guide anchor for ${key}`);
    assert.ok(guide.includes(`### ${key}\n`) || guide.includes(`### ${key}\r\n`), `guide missing ${key}`);
    assert.equal(row[3].includes("●"), !!kwargs.is_core, `core marker for ${key}`);
    assert.equal(row[4].includes("●"), !!(kwargs.is_core || kwargs.default_enabled), `default marker for ${key}`);
  }
  assert.ok(readme.includes(`**${definitions.length} modules**`));
  assert.ok(readme.includes(`each of the ${definitions.length} keys`));
});

test("documented role names match the built-in catalogue without duplicates", () => {
  const catalogue = declarations("backend/apps/makerspaces/role_catalog.py", "RoleDefinition");
  const section = readme.split("## Roles & access\n").pop().split("## Hosting")[0];
  const names = [...section.matchAll(/^\| \*\*([^*]+)\*\* \|/gm)].map((row) => row[1]);
  assert.deepEqual(names, catalogue.map((row) => row.args[1]));
});

test("documented tracking and checkout feature defaults match their declarations", () => {
  const definitions = declarations("backend/apps/makerspaces/capability_definitions.py", "FeatureDefinition");
  const features = new Map(definitions.map((row) => [row.args[0], row]));
  const rows = [...readme.matchAll(/^\| `(charges\.[^`]+|payments\.[^`]+)` \| ([^|]+) \|([^|]*)\|/gm)];
  const expected = definitions.filter((row) => /^(charges|payments)\./.test(row.args[0]));
  assert.equal(rows.length, expected.length);
  for (const [, key, parent, defaultCell] of rows) {
    const definition = features.get(key);
    assert.ok(definition, key);
    assert.equal(parent.trim().replaceAll("`", ""), definition.args[1] ?? "—", key);
    assert.equal(defaultCell.includes("●"), !!definition.kwargs.default_enabled, key);
  }
});

test("Events setup mapping includes the registered signed-read capability", () => {
  const definitions = declarations("backend/apps/makerspaces/capability_definitions_parity.py", "FeatureDefinition");
  assert.equal(definitions.find((row) => row.args[0] === "events.api_read").args[1], "events");
  const eventRow = read("docs/MODULES.md").split(/\r?\n/).find((line) => line.startsWith("| Events |"));
  assert.ok(eventRow.includes("`events.api_read`"));
});

test("README uses supplied horizontal logo masters for light and dark modes", () => {
  const picture = readme.match(/<picture>[\s\S]*?<\/picture>/)?.[0];
  assert.ok(picture);
  assert.match(picture, /media="\(prefers-color-scheme: dark\)"/);
  for (const filename of ["lockup-horizontal.svg", "lockup-horizontal-reversed.svg"]) {
    assert.ok(picture.includes(`docs/brand/${filename}`));
    assert.ok(existsSync(path.join(root, "docs/brand", filename)));
  }
});

test("README local link targets exist", () => {
  const markdown = [...readme.matchAll(/\]\(([^)\s]+)\)/g)].map((match) => match[1]);
  const html = [...readme.matchAll(/(?:href|src|srcset)="([^"]+)"/g)].map((match) => match[1]);
  for (const link of [...markdown, ...html]) {
    if (/^(https?:|#)/.test(link)) continue;
    const target = decodeURIComponent(link.split("#")[0]);
    assert.ok(existsSync(path.join(root, target)), `broken README target: ${link}`);
  }
});

test("release history has one Unreleased section and descending dated entries", () => {
  assert.equal([...read("CHANGELOG.md").matchAll(/^## Unreleased\s*$/gm)].length, 1);
  const dates = [...read("docs/PROJECT-HISTORY.md").matchAll(/^- \*\*(\d{4}-\d{2}-\d{2})/gm)]
    .map((match) => match[1]);
  assert.deepEqual(dates, [...dates].sort().reverse());
});

test("fixed-role invariant references identify real schema, data and constraint migrations", () => {
  const invariants = read("docs/INVARIANTS.md");
  assert.doesNotMatch(invariants, /makerspaces\/0089|Migration 0089/);
  for (const migration of ["0091_fixed_roles_schema", "0092_fixed_roles_data", "0093_fixed_roles_constraint"]) {
    assert.ok(existsSync(path.join(root, "backend/apps/makerspaces/migrations", `${migration}.py`)));
    assert.ok(invariants.includes(migration.split("_")[0]));
  }
});
