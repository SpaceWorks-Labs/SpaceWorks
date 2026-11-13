// Static documentation contracts: run with node --test; no Django or services required.
const assert = require("node:assert/strict");
const { readFileSync, existsSync, readdirSync } = require("node:fs");
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

test("borrow-request matrix in the sign-in guide follows the access-policy resolver", () => {
  // The README no longer carries the matrix (0.12.0 moved it to docs/sign-in-and-borrowing.md), and
  // request_access.py now exposes effective_policy(makerspace), which needs Django, so the resolver's
  // three outcomes are read from its constants and the documented rows are compared with them.
  const source = read("backend/apps/makerspaces/request_access.py");
  for (const mode of ["MEMBERS", "ACCOUNTS", "CONTACT"]) assert.match(source, new RegExp(`^${mode} = "`, "m"));
  const guide = read("docs/sign-in-and-borrowing.md");
  const section = guide.split("| Member accounts (`member_accounts`) | Membership (`membership`) | Who may submit |")[1];
  assert.ok(section, "the matrix must name member_accounts and membership");
  const rows = [...section.split(/\r?\n\r?\n/)[0].matchAll(/^\| (on|off) \| (on|off)[^|]*\| \*\*([^*]+)\*\*/gm)];
  assert.deepEqual(rows.map((row) => [row[1], row[2], row[3]]), [
    ["on", "on", "Members"], ["on", "off", "Account holders"], ["off", "off", "Everyone, no account"],
  ]);
});

test("README module inventory matches the registry and the guide", () => {
  const section = readme.split("\n## Modules\n")[1].split("\n## ")[0];
  const keys = [...section.matchAll(/\[`([^`]+)`\]\(docs\/MODULES\.md#([^)]*)\)/g)];
  assert.equal(new Set(keys.map((k) => k[1])).size, keys.length, "duplicate module link");
  const guide = read("docs/MODULES.md");
  for (const [, key, anchor] of keys) {
    assert.equal(anchor, key, `wrong guide anchor for ${key}`);
    assert.ok(guide.includes(`### ${key}\n`) || guide.includes(`### ${key}\r\n`), `guide missing ${key}`);
  }
  // The registry appends presence, analytics and the shop from sibling modules, so the base catalogue is
  // a subset of the README keys; the README total is the full registry.
  const catalogue = declarations("backend/apps/makerspaces/module_registry_catalog.py", "ModuleDefinition");
  for (const { args: [key] } of catalogue) assert.ok(keys.some((k) => k[1] === key), `README missing ${key}`);
  for (const key of ["presence", "analytics", "shop"]) assert.ok(keys.some((k) => k[1] === key), `README missing ${key}`);
  assert.ok(section.includes(`**${keys.length} modules**`), "README module count");
  const core = catalogue.filter(({ kwargs }) => kwargs.is_core).length;
  assert.ok(section.includes(`**${core} core**`), "README core count");
});

test("documented role names match the built-in catalogue without duplicates", () => {
  const catalogue = declarations("backend/apps/makerspaces/role_catalog.py", "RoleDefinition");
  const section = readme.split("## Roles and access\n").pop().split(/^## /m)[0];
  const names = [...section.matchAll(/^\| \*\*([^*]+)\*\* \|/gm)].map((row) => row[1]);
  assert.deepEqual(names, catalogue.map((row) => row.args[1]));
});

test("documented tracking and checkout feature defaults match their declarations", () => {
  // Feature definitions are spread over capability_definitions*.py, so every sibling file is read.
  const dir = path.join(root, "backend/apps/makerspaces");
  const definitions = readdirSync(dir).filter((name) => /^capability_definitions.*\.py$/.test(name))
    .flatMap((name) => ["FeatureDefinition", "feature"].flatMap((ctor) =>
      declarations(`backend/apps/makerspaces/${name}`, ctor).map((row) => ({ ...row, ctor }))));
  const features = new Map(definitions.map((row) => [row.args[0], row]));
  // The per-feature table moved from the README to the module guide.
  const rows = [...read("docs/MODULES.md").matchAll(/^\| `(charges\.[^`]+|payments\.[^`]+)` \| ([^|]+) \|([^|]*)\|/gm)];
  const expected = definitions.filter((row) => /^(charges|payments)\./.test(row.args[0]));
  assert.equal(rows.length, expected.length);
  for (const [, key, parent, defaultCell] of rows) {
    const definition = features.get(key);
    assert.ok(definition, key);
    // feature(...) passes the parent as a variable the AST reader cannot resolve, so only literals are compared.
    if (definition.ctor === "FeatureDefinition") {
      assert.equal(parent.trim().replaceAll("`", ""), definition.args[1] ?? "—", key);
    }
    assert.equal(defaultCell.includes("●"), !!definition.kwargs.default_enabled, key);
  }
});

test("Events setup mapping includes the registered signed-read capability", () => {
  const definitions = declarations("backend/apps/makerspaces/capability_definitions_parity.py", "FeatureDefinition");
  assert.equal(definitions.find((row) => row.args[0] === "events.api_read").args[1], "events");
  const eventRow = read("docs/MODULES.md").split(/\r?\n/).find((line) => line.startsWith("| Events |"));
  assert.ok(eventRow.includes("`events.api_read`"));
});

test("README banner has light and dark variants", () => {
  // 0.12.0 replaced the horizontal lockup header with branded banners under docs/readme/.
  const picture = readme.match(/<picture>[\s\S]*?<\/picture>/)?.[0];
  assert.ok(picture);
  assert.match(picture, /media="\(prefers-color-scheme: dark\)"/);
  for (const filename of ["banner.svg", "banner-dark.svg"]) {
    assert.ok(picture.includes(`docs/readme/${filename}`));
    assert.ok(existsSync(path.join(root, "docs/readme", filename)));
  }
  for (const filename of ["lockup-horizontal.svg", "lockup-horizontal-reversed.svg"]) {
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
