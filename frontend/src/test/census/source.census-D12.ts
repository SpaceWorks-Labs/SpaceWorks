/// <reference types="node" />
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { resolve, dirname, relative } from "node:path";
import ts from "typescript";

// Vite rewrites import.meta.url to an HTTP URL in jsdom. Filesystem discovery must
// use the runner's working directory, not the browser's URL constructor or origin.
function frontendRoot() {
  for (let directory = resolve(process.cwd()); ; directory = dirname(directory)) {
    for (const candidate of [directory, resolve(directory, "frontend")]) {
      if (existsSync(resolve(candidate, "openapi-schema.json")) && existsSync(resolve(candidate, "src/App.tsx"))) return candidate;
    }
    if (dirname(directory) === directory) throw new Error("D12 cannot locate the frontend source/schema root.");
  }
}
export const ROOT = frontendRoot();
export const SRC = resolve(ROOT, "src");
export type Mode = "single" | "central";
export type RouteCase = { id: string; file: string; line: number; pattern: string;
  screen: string; mode: Mode; path: string; leaves?: string[]; platform?: boolean; memberTab?: string };
type Env = Record<string, unknown>;
const parsed = new Map<string, ts.SourceFile>();
export function source(file: string) {
  if (!parsed.has(file)) parsed.set(file, ts.createSourceFile(file, readFileSync(file, "utf8"),
    ts.ScriptTarget.Latest, true, file.endsWith("tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS));
  return parsed.get(file)!;
}
export function sourceFiles(directory = SRC): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const full = resolve(directory, entry.name);
    if (entry.isDirectory()) return /^(test|__tests__|generated|locales)$/.test(entry.name) ? [] : sourceFiles(full);
    return /\.tsx?$/.test(entry.name) && !/\.(test|spec|dev)\.|\.d\.ts$/.test(entry.name) ? [full] : [];
  }).sort();
}
function moduleFile(from: string, specifier: string) {
  const base = resolve(dirname(from), specifier);
  const file = [base, `${base}.ts`, `${base}.tsx`, resolve(base, "index.ts"), resolve(base, "index.tsx")]
    .find(candidate => existsSync(candidate) && /\.tsx?$/.test(candidate));
  if (!file) throw new Error(`D12 cannot resolve ${specifier} from ${from}`);
  return file;
}
function binding(name: string, file: string, env: Env): unknown {
  if (Object.prototype.hasOwnProperty.call(env, name)) return env[name];
  let found: ts.Expression | undefined;
  let imported: { file: string; name: string } | undefined;
  const scan = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && node.name.getText() === name) found = node.initializer;
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)
        && node.moduleSpecifier.text.startsWith(".")) {
      const imports = node.importClause?.namedBindings;
      if (imports && ts.isNamedImports(imports)) for (const item of imports.elements) {
        if (item.name.text === name) imported = { file: moduleFile(file, node.moduleSpecifier.text),
          name: item.propertyName?.text ?? item.name.text };
      }
    }
    ts.forEachChild(node, scan);
  };
  scan(source(file));
  if (found) return value(found, file, env);
  if (imported) return binding(imported.name, imported.file, {});
  throw new Error(`D12 unresolved route binding ${name} in ${file}`);
}
export function value(node: ts.Expression, file: string, env: Env = {}): unknown {
  if (ts.isAsExpression(node) || ts.isParenthesizedExpression(node) || ts.isSatisfiesExpression(node)) return value(node.expression, file, env);
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (ts.isIdentifier(node)) return binding(node.text, file, env);
  if (ts.isArrayLiteralExpression(node)) return node.elements.flatMap(element =>
    ts.isSpreadElement(element) ? value(element.expression, file, env) as unknown[] : [value(element, file, env)]);
  if (ts.isObjectLiteralExpression(node)) return Object.fromEntries(node.properties.map(property => {
    if (!ts.isPropertyAssignment(property)) throw new Error(`D12 unsupported property ${property.getText()}`);
    return [property.name.getText().replace(/^["']|["']$/g, ""), value(property.initializer, file, env)];
  }));
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken)
    return String(value(node.left, file, env)) + String(value(node.right, file, env));
  if (ts.isTemplateExpression(node)) return node.head.text + node.templateSpans.map(span =>
    String(value(span.expression, file, env)) + span.literal.text).join("");
  if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
      && ["map", "flatMap"].includes(node.expression.name.text)) {
    const fn = node.arguments[0];
    if (!ts.isArrowFunction(fn) || ts.isBlock(fn.body)) throw new Error(`D12 unsupported map ${node.getText()}`);
    const items = value(node.expression.expression, file, env) as unknown[];
    const mapped = items.map(item => value(fn.body as ts.Expression, file, { ...env, [fn.parameters[0].name.getText()]: item }));
    return node.expression.name.text === "flatMap" ? mapped.flat() : mapped;
  }
  throw new Error(`D12 unsupported route expression ${node.getText()} in ${file}`);
}
const SAMPLES: Record<string, string> = {
  slug: "lab", organizationSlug: "d12-org", programmeSlug: "d12-programme", productSlug: "d12-product",
  memberTab: "loans", view: "request", sectionId: "member", articleSlug: "d12-missing-article", module: "events",
  handle: "d12-maker", campaign: "d12-campaign", sessionSlug: "d12-session", speakerSlug: "d12-speaker",
  obligationId: "11111111-1111-4111-8111-111111111111", verificationId: "11111111-1111-4111-8111-111111111111",
};
export function concrete(pattern: string) {
  const path = pattern.replace(/:([\w]+)\??/g, (_, name: string) => SAMPLES[name]
    ?? (/Id$/.test(name) ? "1" : "11111111-1111-4111-8111-111111111111"))
    .replace(/\*$/, pattern === "*" ? "d12-unknown" : "").replace(/\/$/, "");
  return path.startsWith("/") ? path : `/${path}`;
}
function modes(node: ts.Node, file: string): Mode[] {
  if (!file.endsWith("AppRoutes.tsx")) return ["single", "central"];
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (ts.isIfStatement(parent) && parent.expression.getText() === 'mode === "single"')
      return node.pos >= parent.thenStatement.pos && node.end <= parent.thenStatement.end ? ["single"] : ["central"];
  }
  return ["single", "central"];
}
function screenNames(node: ts.Node | undefined): string[] {
  if (!node) throw new Error("D12 missing route element");
  if (ts.isJsxExpression(node) || ts.isParenthesizedExpression(node)) return screenNames(node.expression);
  if (ts.isConditionalExpression(node)) return [...screenNames(node.whenTrue), ...screenNames(node.whenFalse)];
  if (ts.isJsxSelfClosingElement(node)) return [node.tagName.getText()];
  if (ts.isJsxElement(node)) {
    const tag = node.openingElement.tagName.getText();
    if (tag === "Suspense") return node.children.flatMap(child =>
      ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child) ? screenNames(child) : []);
    return [tag];
  }
  if (ts.isIdentifier(node) && node.text === "landing") return ["LandingGate"];
  throw new Error(`D12 unsupported route element ${node.getText()}`);
}
function staffLeaves() {
  const leaves: Record<string, Set<string>> = {};
  const loaders = source(resolve(SRC, "features/staff/StaffTabLoaders.tsx"));
  const renderedNames = new Map<string, string>();
  const loader = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      const exported = /default:\s*\w+\.(\w+)/.exec(node.initializer.getText());
      if (exported) renderedNames.set(node.name.text, exported[1]);
    }
    ts.forEachChild(node, loader);
  };
  loader(loaders);
  for (const file of ["features/staff/StaffTabContent.tsx", "features/staff/StaffPlatformTabContent.tsx",
    "features/staff/platformConsole/PlatformConsoleContent.tsx"]) {
    const sf = source(resolve(SRC, file));
    const branches = (node: ts.Node) => {
      const condition = ts.isIfStatement(node) ? node.expression : ts.isConditionalExpression(node) ? node.condition : undefined;
      const body = ts.isIfStatement(node) ? node.thenStatement : ts.isConditionalExpression(node) ? node.whenTrue : undefined;
      if (condition && body) for (const match of condition.getText().matchAll(/activeTab === "([\w-]+)"/g)) {
        const tab = match[1];
        leaves[tab] ??= new Set();
        const children = (child: ts.Node) => {
          if (ts.isJsxOpeningElement(child) || ts.isJsxSelfClosingElement(child)) {
            const name = child.tagName.getText();
            if (/^[A-Z]\w*$/.test(name) && !["StaffPanelErrorBoundary", "Suspense", "LogoLoader", "ListLayout", "PiiAccessBanner"].includes(name))
              leaves[tab].add(renderedNames.get(name) ?? name);
          }
          ts.forEachChild(child, children);
        };
        children(body);
      }
      ts.forEachChild(node, branches);
    };
    branches(sf);
  }
  return Object.fromEntries(Object.entries(leaves).map(([tab, names]) => [tab, [...names].sort()]));
}
export function routeInventory(): RouteCase[] {
  const output: RouteCase[] = [];
  const relativeRoutes: Omit<RouteCase, "id" | "mode">[] = [];
  for (const file of sourceFiles().filter(file => file.endsWith(".tsx"))) {
    const sf = source(file);
    if (!sf.text.includes("<Route")) continue;
    const walk = (node: ts.Node, env: Env = {}) => {
      // App has three production utility screens selected before its JSX route trees.
      if (file === resolve(SRC, "App.tsx") && ts.isIfStatement(node)) {
        const returned = ts.isReturnStatement(node.thenStatement) ? node.thenStatement.expression : undefined;
        const screen = returned ? screenNames(returned)[0] : undefined;
        if (screen && !["AppRoutes", "ChartTestPage", "LogoLoader", "PausedSpacePage", "CenteredCardLayout", "Routes"].includes(screen)) {
          const paths: string[] = [];
          const comparisons = (part: ts.Node) => {
            if (ts.isBinaryExpression(part) && part.left.getText() === "pathname"
                && part.operatorToken.kind === ts.SyntaxKind.EqualsEqualsEqualsToken)
              paths.push(String(value(part.right, file, env)));
            ts.forEachChild(part, comparisons);
          };
          comparisons(node.expression);
          for (const pattern of paths) for (const mode of ["single", "central"] as const) {
            const line = sf.getLineAndCharacterOfPosition(node.getStart()).line + 1;
            output.push({ file: "App.tsx", line, pattern, path: concrete(pattern), screen, mode,
              id: `App.tsx:${line}:${mode}:${pattern}` });
          }
        }
      }
      if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
          && ["map", "flatMap"].includes(node.expression.name.text)) {
        const fn = node.arguments[0];
        // Only evaluate callbacks which contain routes. Other maps can depend on live data.
        if (fn && ts.isArrowFunction(fn) && /<Route\b/.test(fn.body.getText())) {
          const items = value(node.expression.expression, file, env) as unknown[];
          for (const item of items) walk(fn.body, { ...env, [fn.parameters[0].name.getText()]: item });
          return;
        }
      }
      if ((ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) && node.tagName.getText() === "Route") {
        const attrs = node.attributes.properties;
        const attr = (name: string) => attrs.find(item => ts.isJsxAttribute(item) && item.name.getText() === name) as ts.JsxAttribute | undefined;
        const path = attr("path")?.initializer;
        const pattern = path ? String(ts.isStringLiteral(path) ? path.text :
          ts.isJsxExpression(path) && path.expression ? value(path.expression, file, env) : undefined) : "";
        if (!path && !attr("index")) throw new Error(`D12 Route without path/index: ${file}:${node.pos}`);
        const element = attr("element")?.initializer;
        for (const declared of screenNames(element)) {
        // A lazy binding's variable name need not be the mounted export name.
        const lazyPages = source(resolve(SRC, "AppRoutesLazyPages.tsx"));
        const exported = lazyPages.statements.filter(ts.isVariableStatement)
          .flatMap(statement => [...statement.declarationList.declarations]).find(item => item.name.getText() === declared);
        const screen = exported?.initializer?.getText().match(/default:\s*\w+\.(\w+)/)?.[1] ?? declared;
        const row = { file: relative(SRC, file).split("\\").join("/"),
          line: sf.getLineAndCharacterOfPosition(node.getStart()).line + 1, pattern, screen, path: concrete(pattern) };
        if (row.file === "features/events/programme/EventProgrammePage.tsx"
            || pattern && !pattern.startsWith("/") && pattern !== "*" || !pattern) relativeRoutes.push(row);
        else for (const mode of modes(node, file)) output.push({ ...row, mode, id: `${row.file}:${row.line}:${mode}:${pattern}:${screen}` });
        }
      }
      ts.forEachChild(node, child => walk(child, env));
    };
    walk(sf);
  }
  // EventProgrammePage owns relative child routes below the two registry-derived programme roots.
  const roots = output.filter(row => row.screen === "EventProgrammePage");
  for (const row of relativeRoutes) {
    if (row.file !== "features/events/programme/EventProgrammePage.tsx")
      throw new Error(`D12 new relative route requires a parent binding: ${row.file}:${row.line}`);
    for (const root of roots) {
      const pattern = root.pattern.replace(/\*$/, row.pattern);
      output.push({ ...row, pattern, path: row.screen === "p" ? `${concrete(pattern)}/d12-unknown` : concrete(pattern), mode: root.mode,
        id: `${row.file}:${row.line}:${root.mode}:${pattern}:${row.screen}` });
    }
  }
  // Wildcard admin entries are dispatchers: enumerate their registered screens as well as their root.
  const tabs = binding("ALL_TABS", resolve(SRC, "features/staff/staffAccess.ts"), {}) as string[];
  const aliases = binding("TAB_PATHS", resolve(SRC, "features/staff/staffTabs.ts"), {}) as Record<string, string>;
  const platformOnly = binding("PLATFORM_ONLY_TABS", resolve(SRC, "features/staff/staffAccess.ts"), {}) as string[];
  const centralOnly = new Set<string>();
  const access = (node: ts.Node) => {
    if (ts.isIfStatement(node) && ts.isReturnStatement(node.thenStatement)
      && node.thenStatement.expression?.getText().includes("!singleTenantLocked")) {
      const tab = /^tabName === "([\w-]+)"$/.exec(node.expression.getText());
      if (tab) centralOnly.add(tab[1]);
    }
    ts.forEachChild(node, access);
  };
  access(source(resolve(SRC, "features/staff/staffAccess.ts")));
  const leaves = staffLeaves();
  for (const parent of output.filter(row => row.screen === "StaffApp")) for (const tab of tabs) {
    if (parent.mode === "single" && (platformOnly.includes(tab) || centralOnly.has(tab))) continue;
    const pattern = parent.pattern.replace(/\*$/, aliases[tab] ?? tab);
    output.push({ ...parent, pattern, path: concrete(pattern), screen: `StaffApp/${tab}`, id: `${parent.id}/${tab}`,
      leaves: leaves[tab] ?? [], platform: platformOnly.includes(tab) || tab === "migration" });
  }
  const memberTabs = binding("MEMBER_TABS", resolve(SRC, "features/members/MemberPortalTabs.tsx"), {}) as string[];
  for (const parent of output.filter(row => row.screen === "MemberTabRoute")) for (const tab of memberTabs) {
    const pattern = parent.pattern.replace(":memberTab", tab === "account" ? "account-portal" : tab);
    output.push({ ...parent, pattern, path: concrete(pattern), screen: `MemberArea/${tab}`,
      id: `${parent.id}/${tab}`, memberTab: tab });
  }
  return output.sort((a, b) => a.id.localeCompare(b.id));
}
