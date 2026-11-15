import ts from "typescript";
import { source, sourceFiles, type RouteCase } from "./source.census-D12";

type Command = { path: string; body: unknown; fragment: string; button: string; idle: string };
const declarations = new Map<string, ts.SourceFile>();
for (const file of sourceFiles()) {
  const sf = source(file);
  for (const statement of sf.statements) {
    if (ts.isFunctionDeclaration(statement) && statement.name) declarations.set(statement.name.text, sf);
  }
}
const cache = new Map<string, Command | undefined>();
const PROOF = "d12-enrollment-proof";

// A small, deliberately closed interpreter for one-click commands. It derives
// the method, JSON payload and real button from useMutation + JSX, not route
// names. Passwords, file uploads, choices and arbitrary function calls remain
// unsupported instead of submitting a guessed business action.
export function commandFromSource(row: RouteCase): Command | undefined {
  if (cache.has(row.id)) return cache.get(row.id);
  const sf = declarations.get(row.screen.split("/")[0]);
  if (!sf) return undefined;
  const params: Record<string, string> = {};
  row.pattern.split("/").forEach((part, index) => {
    if (part.startsWith(":")) params[part.slice(1).replace(/\?$/, "")] = row.path.split("/")[index];
  });
  let needsFragment = false;
  const evaluate = (node: ts.Node): unknown => {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
    if (ts.isNumericLiteral(node)) return Number(node.text);
    if (node.kind === ts.SyntaxKind.TrueKeyword) return true;
    if (node.kind === ts.SyntaxKind.FalseKeyword) return false;
    if (ts.isTaggedTemplateExpression(node) || ts.isParenthesizedExpression(node))
      return evaluate(ts.isTaggedTemplateExpression(node) ? node.template : node.expression);
    if (ts.isIdentifier(node)) {
      if (params[node.text] !== undefined) return params[node.text];
      if (node.text === "token" && /location\.hash/.test(sf.text)) { needsFragment = true; return PROOF; }
    }
    if (ts.isTemplateExpression(node)) return node.head.text + node.templateSpans.map(span => String(evaluate(span.expression)) + span.literal.text).join("");
    if (ts.isCallExpression(node) && node.expression.getText() === "encodeURIComponent") return encodeURIComponent(String(evaluate(node.arguments[0])));
    if (ts.isObjectLiteralExpression(node)) return Object.fromEntries(node.properties.map(property => {
      if (ts.isShorthandPropertyAssignment(property)) return [property.name.text, evaluate(property.name)];
      if (ts.isPropertyAssignment(property)) return [property.name.getText().replace(/^["']|["']$/g, ""), evaluate(property.initializer)];
      throw new Error("Unsupported command property");
    }));
    throw new Error("Command requires an explicit browser interaction adapter");
  };
  const walk = (node: ts.Node, callback: (node: ts.Node) => void) => { callback(node); ts.forEachChild(node, child => walk(child, callback)); };
  const initialCopy = (node: ts.Node): string | undefined => {
    if (ts.isConditionalExpression(node)) return initialCopy(node.whenFalse);
    if (ts.isJsxExpression(node) && node.expression) return initialCopy(node.expression);
    if (ts.isJsxElement(node)) {
      const parts = node.children.map(child => ts.isJsxText(child) ? child.text.trim() : initialCopy(child));
      return parts.every(part => part !== undefined) ? parts.join("") : undefined;
    }
    try { const value = evaluate(node); return typeof value === "string" ? value : undefined; } catch { return undefined; }
  };
  let command: Command | undefined;
  walk(sf, node => {
    if (command || !ts.isVariableDeclaration(node) || !ts.isIdentifier(node.name) || !node.initializer
      || !ts.isCallExpression(node.initializer) || node.initializer.expression.getText() !== "useMutation") return;
    const options = node.initializer.arguments[0];
    if (!options || !ts.isObjectLiteralExpression(options)) return;
    const fn = options.properties.find(property => ts.isPropertyAssignment(property) && property.name.getText() === "mutationFn");
    if (!fn || !ts.isPropertyAssignment(fn) || !ts.isArrowFunction(fn.initializer) || fn.initializer.parameters.length) return;
    const mutationName = node.name.text;
    // A mutation the screen fires from useEffect is not a user command (its Retry
    // label only re-runs that effect's request); effectFor/checkActionRequest own it.
    let effectDriven = false;
    walk(sf, call => {
      if (ts.isCallExpression(call) && call.expression.getText() === "useEffect"
        && call.arguments[0]?.getText().includes(`${mutationName}.mutate(`)) effectDriven = true;
    });
    if (effectDriven) return;
    walk(fn.initializer.body, request => {
      if (command || !ts.isCallExpression(request) || !/^(publicV1Request|staffRequest|memberRequest)$/.test(request.expression.getText())) return;
      const init = request.arguments[1];
      if (!init || !ts.isObjectLiteralExpression(init)) return;
      const fields = new Map(init.properties.filter(ts.isPropertyAssignment).map(property => [property.name.getText(), property.initializer]));
      try {
        if (evaluate(fields.get("method")!) !== "POST") return;
        const body = fields.get("body");
        if (!body || !ts.isCallExpression(body) || body.expression.getText() !== "JSON.stringify") return;
        const path = String(evaluate(request.arguments[0])).replace(/\/$/, "");
        const payload = evaluate(body.arguments[0]);
        let button: string | undefined, idle: string | undefined;
        walk(sf, child => {
          if (ts.isPropertyAssignment(child) && child.name.getText() === "onClick" && child.initializer.getText().includes(`${mutationName}.mutate()`)) {
            const parent = child.parent;
            if (ts.isObjectLiteralExpression(parent)) {
              const label = parent.properties.find(property => ts.isPropertyAssignment(property) && property.name.getText() === "label");
              if (label && ts.isPropertyAssignment(label)) button = initialCopy(label.initializer);
            }
          }
          if (ts.isJsxAttribute(child) && child.name.getText() === "body" && child.initializer) idle = initialCopy(child.initializer);
        });
        if (button && idle) command = { path, body: payload, fragment: needsFragment ? `#token=${PROOF}` : "", button, idle };
      } catch { /* A missing adapter remains an ordinary census failure. */ }
    });
  });
  cache.set(row.id, command);
  return command;
}
