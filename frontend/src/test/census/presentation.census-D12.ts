import ts from "typescript";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { source, sourceFiles, type RouteCase } from "./source.census-D12";
import { exportedSources } from "./exports.census-D12";
import { REFUSALS } from "./fetch.census-D12";

const modules = new Map<string, ts.SourceFile[]>();
for (const file of sourceFiles()) {
  const sf = source(file);
  for (const statement of sf.statements) {
    const names = ts.isFunctionDeclaration(statement) && statement.name ? [statement.name.text]
      : ts.isVariableStatement(statement) ? statement.declarationList.declarations
        .filter(declaration => ts.isIdentifier(declaration.name) && declaration.initializer
          && (ts.isArrowFunction(declaration.initializer) || ts.isFunctionExpression(declaration.initializer)))
        .map(declaration => declaration.name.getText()) : [];
    for (const name of names) modules.set(name, [...modules.get(name) ?? [], sf]);
  }
}
const cache = new Map<string, string[]>();
// EmptyState.message and layout.empty.message are explicit product presentation
// contracts. Read their static literals per screen instead of maintaining a second
// catalogue of hundreds of sentences. Interpolated messages need a data adapter.
export function emptyCopyFor(row: RouteCase) {
  const names = row.leaves?.length ? row.leaves : [row.screen.split("/")[0]];
  return [...new Set(names.flatMap(name => {
    if (cache.has(name)) return cache.get(name)!;
    const messages: string[] = [];
    for (const sf of modules.get(name) ?? []) {
      const values = new Map<string, ts.Expression>();
      const declarations = (node: ts.Node) => {
        if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) values.set(node.name.text, node.initializer);
        ts.forEachChild(node, declarations);
      };
      declarations(sf);
      const literals = (node: ts.Node) => {
        if (ts.isNoSubstitutionTemplateLiteral(node) || ts.isStringLiteral(node)) messages.push(node.text);
        // Conditional messages are both concrete product contracts; don't admit
        // unrelated props in an EmptyState or layout's rows.
        else if (ts.isTaggedTemplateExpression(node)) literals(node.template);
        else if (ts.isConditionalExpression(node)) { literals(node.whenTrue); literals(node.whenFalse); }
        else if (ts.isIdentifier(node)) {
          const value = values.get(node.text);
          if (value && value !== node) literals(value);
        }
      };
      const visit = (node: ts.Node) => {
        if ((ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) && node.tagName.getText() === "EmptyState") {
          const attribute = node.attributes.properties.find(item => ts.isJsxAttribute(item) && item.name.getText() === "message");
          if (attribute && ts.isJsxAttribute(attribute) && attribute.initializer) {
            const input = attribute.initializer;
            if (ts.isJsxExpression(input) && input.expression) literals(input.expression); else literals(input);
          }
        }
        if (ts.isPropertyAssignment(node) && node.name.getText() === "message") {
          const parent = node.parent.parent;
          if (ts.isJsxExpression(parent) && ts.isJsxAttribute(parent.parent) && parent.parent.name.getText() === "empty") literals(node.initializer);
          if (ts.isPropertyAssignment(parent) && parent.name.getText() === "empty") literals(node.initializer);
        }
        ts.forEachChild(node, visit);
      };
      visit(sf);
    }
    cache.set(name, [...new Set(messages)]);
    return cache.get(name)!;
  }))];
}

const stateCache = new Map<string, string[]>();
const retryCache = new Map<string, Set<string>>();
// These exact strings come only from error/empty branches and presentation slots
// in the target's import closure. A heading in an ordinary ready state is never
// sufficient evidence of an error. Dynamic interpolations remain unsupported.
export function stateCopyFor(row: RouteCase, phase: "empty" | "error" | "permission" | "module") {
  const key = `${row.screen}:${phase}`;
  if (stateCache.has(key)) return stateCache.get(key)!;
  const result = new Set<string>();
  const retries = retryCache.get(row.screen) ?? new Set<string>();
  retryCache.set(row.screen, retries);
  const visited = new Set<string>();
  const condition = phase === "empty" ? /empty|not.?found|missing|gone|removed|\.length\s*(?:===?|<)|!.*\.length|!\w+\.data/i : /error|refused|denied|disabled|unavailable|gone|removed|!.*\.ok/i;
  const read = (sf: ts.SourceFile) => {
    if (visited.has(sf.fileName)) return;
    visited.add(sf.fileName);
    // Missing query-derived locals (!team, !own, !data) are absence branches
    // too. Limit this to declarations derived from actual query data.
    const absent = new Set<string>();
    const initializers = new Map<string, ts.Expression>();
    const declarations = (node: ts.Node) => {
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer
        && /\b\w+\.data\b/.test(node.initializer.getText())) absent.add(node.name.text);
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) initializers.set(node.name.text, node.initializer);
      ts.forEachChild(node, declarations);
    };
    declarations(sf);
    const isAbsence = (node: ts.Expression) => condition.test(node.getText())
      || ts.isIdentifier(node) && condition.test(initializers.get(node.text)?.getText() ?? "")
      || phase === "empty" && ts.isPrefixUnaryExpression(node) && node.operator === ts.SyntaxKind.ExclamationToken
        && ts.isIdentifier(node.operand) && absent.has(node.operand.text);
    const visit = (node: ts.Node) => {
      if (phase === "empty" && ts.isPropertyAssignment(node) && node.name.getText() === "message"
        && ts.isIdentifier(node.initializer)) {
        const parent = node.parent.parent;
        if (ts.isJsxExpression(parent) && ts.isJsxAttribute(parent.parent) && parent.parent.name.getText() === "empty") {
          const value = initializers.get(node.initializer.text);
          const literals = (input: ts.Node) => {
            if (ts.isStringLiteral(input) || ts.isNoSubstitutionTemplateLiteral(input)) result.add(input.text);
            else if (ts.isTaggedTemplateExpression(input)) literals(input.template);
            else if (ts.isConditionalExpression(input)) { literals(input.whenTrue); literals(input.whenFalse); }
            else if (ts.isElementAccessExpression(input)) literals(input.expression);
            else if (ts.isObjectLiteralExpression(input)) input.properties.filter(ts.isPropertyAssignment).forEach(item => literals(item.initializer));
            else if (ts.isNonNullExpression(input)) literals(input.expression);
          };
          if (value) literals(value);
        }
      }
      const label = (input: ts.Node) => {
        if (ts.isStringLiteral(input) || ts.isNoSubstitutionTemplateLiteral(input)) retries.add(input.text);
        else if (ts.isJsxText(input) && input.text.trim()) retries.add(input.text.trim());
        else if (ts.isConditionalExpression(input)) label(input.whenFalse);
        else if (ts.isJsxElement(input)) input.children.forEach(label);
        else if (ts.isJsxExpression(input) && input.expression) label(input.expression);
        else if (ts.isTaggedTemplateExpression(input)) label(input.template);
      };
      if (ts.isJsxElement(node) && node.openingElement.tagName.getText() === "button") {
        const click = node.openingElement.attributes.properties.find(attribute => ts.isJsxAttribute(attribute) && attribute.name.getText() === "onClick");
        if (click && /refetch|onRetry|\.retry\(/.test(click.getText())) node.children.forEach(label);
      }
      if (ts.isObjectLiteralExpression(node)) {
        const click = node.properties.find(property => ts.isPropertyAssignment(property) && property.name.getText() === "onClick");
        const text = node.properties.find(property => ts.isPropertyAssignment(property) && property.name.getText() === "label");
        if (click && text && ts.isPropertyAssignment(text) && /refetch|onRetry|\.retry\(/.test(click.getText())) label(text.initializer);
      }
      // ErrorText's resource prop is an explicit sentence parameter. Its label
      // is deliberately not an error-slot literal in the caller.
      if (phase !== "empty" && (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node))
        && ["ErrorText", "ErrorBlock"].includes(node.tagName.getText())) {
        const resource = node.attributes.properties.find(item => ts.isJsxAttribute(item) && item.name.getText() === "resource");
        if (resource && ts.isJsxAttribute(resource) && resource.initializer) {
          let value: ts.Node = resource.initializer;
          if (ts.isJsxExpression(value) && value.expression) value = value.expression;
          if (ts.isTaggedTemplateExpression(value)) value = value.template;
          if (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value)) result.add(`Couldn't load ${value.text}. Try again.`);
        }
      }
      if (phase !== "empty" && ts.isCallExpression(node) && /state|error|message/i.test(node.expression.getText())) {
        // Helpers such as opsQueryState(query, "member cards") own a marked
        // sentence whose resource comes from a literal call argument. Resolve
        // only those simple named substitutions; never invent dynamic copy.
        for (const owner of modules.get(node.expression.getText()) ?? []) {
          const fn = owner.statements.find(statement => ts.isFunctionDeclaration(statement) && statement.name?.text === node.expression.getText());
          if (!fn || !ts.isFunctionDeclaration(fn) || !fn.body) continue;
          const values = new Map(fn.parameters.map((parameter, index) => [parameter.name.getText(), node.arguments[index]]));
          const templates = (child: ts.Node) => {
            if (ts.isTemplateExpression(child)) {
              const spans = child.templateSpans.map(span => ({ span, value: values.get(span.expression.getText()) }));
              if (spans.every(({ value }) => value && (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value))))
                result.add(child.head.text + spans.map(({ span, value }) => (value as ts.StringLiteral).text + span.literal.text).join(""));
            }
            ts.forEachChild(child, templates);
          };
          templates(fn.body);
        }
      }
      const interpolated = phase !== "empty" && ts.isTemplateExpression(node)
        && node.templateSpans.every(span => /(?:\.|\?\.)message$/.test(span.expression.getText()))
        ? node.head.text + node.templateSpans.map(span => REFUSALS[phase].detail + span.literal.text).join("") : undefined;
      if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isJsxText(node) || interpolated !== undefined) {
        const text = (interpolated ?? (node as ts.StringLiteral).text).trim();
        if (text && /[A-Za-z]/.test(text)) {
          let hiddenLiteral = false;
          let absenceBody = false;
          let stateBadge = false;
          if (ts.isCaseClause(node.parent) && node.parent.expression === node) hiddenLiteral = true;
          if (ts.isBinaryExpression(node.parent) && [ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken,
            ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken].includes(node.parent.operatorToken.kind)) hiddenLiteral = true;
          for (let owner = node.parent; owner && !ts.isSourceFile(owner); owner = owner.parent) {
            if (ts.isJsxElement(owner) && /^(button|a)$/.test(owner.openingElement.tagName.getText())) { hiddenLiteral = true; break; }
            if (ts.isJsxElement(owner) && /^h[1-6]$/.test(owner.openingElement.tagName.getText())
              && !/\b(no|nothing|not|empty|unavailable|unable|couldn't|missing|unknown|expired|invalid|error|failed|denied)\b/i.test(text)) {
              hiddenLiteral = true; break;
            }
            if (ts.isPropertyAssignment(owner) && owner.name.getText() === "title"
              && !/\b(no|nothing|not|empty|unavailable|unable|couldn't|missing|unknown|expired|invalid|error|failed|denied)\b/i.test(text)) {
              hiddenLiteral = true; break;
            }
            if (ts.isPropertyAssignment(owner) && /^(error|errorMessage|emptyText|emptyMessage|message|body|title)$/.test(owner.name.getText())) break;
            if (ts.isJsxAttribute(owner)) {
              const element = owner.parent.parent;
              stateBadge = owner.name.getText() === "label" && (ts.isJsxOpeningElement(element) || ts.isJsxSelfClosingElement(element))
                && element.tagName.getText() === "StatusPill" && /^(No |Nothing |Couldn't |Unable )|unavailable\.?$/i.test(text);
              absenceBody = /^(body|content)$/.test(owner.name.getText());
              hiddenLiteral = !stateBadge && !/^(body|content|title|message|error|errorMessage|empty|emptyText|emptyMessage)$/.test(owner.name.getText()); break;
            }
            if (ts.isPropertyAssignment(owner) && /^(label|className|status|code|key|href|tone|icon)$/.test(owner.name.getText())) {
              hiddenLiteral = true; break;
            }
          }
          if (hiddenLiteral) return;
          if (stateBadge && (phase === "empty" ? /^(No |Nothing )/i.test(text) : /Couldn't|Unable|unavailable/i.test(text))) result.add(text);
          for (let parent = node.parent; parent && !ts.isSourceFile(parent); parent = parent.parent) {
            // A retry button, CSS class or status identifier cannot stand in
            // for the explanation that accompanies that state.
            if (ts.isJsxAttribute(parent) && !/^(body|content|title|message|error|errorMessage|empty|emptyText|emptyMessage)$/.test(parent.name.getText())) break;
            if (ts.isPropertyAssignment(parent) && /^(label|className|status|code|key|href|tone|icon)$/.test(parent.name.getText())) break;
            if (ts.isPropertyAssignment(parent) && (phase === "empty" ? /^(emptyText|emptyMessage)$/.test(parent.name.getText())
              : /^(error|errorMessage)$/.test(parent.name.getText()))) { result.add(text); break; }
            if (/^(retry|try again|check again|reload|object|string|number|boolean|undefined|error|loading|empty|ready)$/i.test(text)) break;
            if (ts.isConditionalExpression(parent) && isAbsence(parent.condition)
              && node.pos >= parent.whenTrue.pos && node.end <= parent.whenTrue.end
              || ts.isIfStatement(parent) && isAbsence(parent.expression)
                && node.pos >= parent.thenStatement.pos && node.end <= parent.thenStatement.end
              || ts.isBinaryExpression(parent) && parent.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken
                && isAbsence(parent.left) && node.pos >= parent.right.pos
              || absenceBody && ts.isConditionalExpression(parent) && /^(data|\w+\.data)$/.test(parent.condition.getText())
                && node.pos >= parent.whenFalse.pos && node.end <= parent.whenFalse.end
              || phase === "empty" && ts.isConditionalExpression(parent) && ts.isIdentifier(parent.condition)
                && absent.has(parent.condition.text) && node.pos >= parent.whenFalse.pos && node.end <= parent.whenFalse.end
              || phase !== "empty" && ts.isFunctionDeclaration(parent) && /error|message/i.test(parent.name?.text ?? "")
              || phase !== "empty" && ts.isCatchClause(parent)
              || phase === "empty" && ts.isJsxAttribute(parent) && parent.name.getText() === "message"
                && (ts.isJsxOpeningElement(parent.parent.parent) || ts.isJsxSelfClosingElement(parent.parent.parent))
                && parent.parent.parent.tagName.getText() === "EmptyState"
              || ts.isJsxAttribute(parent) && (phase === "empty" ? /^(empty|emptyText|emptyMessage)$/.test(parent.name.getText())
                : /^(error|errorMessage)$/.test(parent.name.getText()))) {
              result.add(text); break;
            }
          }
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sf);
    for (const statement of sf.statements) {
      if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)
        || !statement.moduleSpecifier.text.startsWith(".")) continue;
      const base = resolve(dirname(sf.fileName), statement.moduleSpecifier.text);
      const file = [base + ".tsx", base + ".ts", resolve(base, "index.ts"), resolve(base, "index.tsx")].find(existsSync);
      // Dispatch barrels import every screen; recurse only within the screen's
      // own feature and shared components, rather than accepting other screens' copy.
      // TypeScript normalises SourceFile.fileName to forward slashes. On Windows,
      // resolve() returns backslashes: comparing dirname strings dropped EVERY
      // sibling import, including DirectoryError and opsQueryState's resource copy.
      const feature = resolve(sf.fileName).split(/[\\/]/).indexOf("features");
      const root = feature < 0 ? undefined : resolve(sf.fileName).split(/[\\/]/).slice(0, feature + 2).join("/");
      const normalized = file && resolve(file).replace(/\\/g, "/");
      const names = statement.importClause?.namedBindings;
      const child = names && ts.isNamedImports(names) && names.elements.some(binding =>
        new RegExp(`<${binding.name.text}(?:\\s|/|>)`).test(sf.text));
      if (file && names && ts.isNamedImports(names)) for (const binding of names.elements) {
        if (new RegExp(`<${binding.name.text}(?:\\s|/|>)`).test(sf.text))
          for (const target of exportedSources(file, binding.propertyName?.text ?? binding.name.text)) read(target);
      }
      if (file && (child || resolve(dirname(file)) === resolve(dirname(sf.fileName)) || file.includes("components")
        || root && normalized?.startsWith(`${root}/`))) read(source(file));
    }
  };
  for (const name of row.leaves?.length ? row.leaves : [row.screen.split("/")[0]])
    for (const sf of modules.get(name) ?? []) read(sf);
  stateCache.set(key, [...result]);
  return [...result];
}
export function retryCopyFor(row: RouteCase) {
  stateCopyFor(row, "error");
  return [...retryCache.get(row.screen) ?? []];
}
