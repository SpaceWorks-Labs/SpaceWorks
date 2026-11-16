import ts from "typescript";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { source, sourceFiles } from "./source.census-D12";

const PARAM = "__D12_PARAMETER__";
const candidates: { match: RegExp; weight: number; type: ts.TypeNode; file: ts.SourceFile }[] = [];
function imported(sf: ts.SourceFile, name: string): { file: ts.SourceFile; name: string } | undefined {
  for (const statement of sf.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)
      || !statement.moduleSpecifier.text.startsWith(".")) continue;
    const bindings = statement.importClause?.namedBindings;
    if (!bindings || !ts.isNamedImports(bindings)) continue;
    const binding = bindings.elements.find(item => item.name.text === name);
    if (!binding) continue;
    const base = resolve(dirname(sf.fileName), statement.moduleSpecifier.text);
    const file = [base + ".ts", base + ".tsx", resolve(base, "index.ts")].find(existsSync);
    if (file) return { file: source(file), name: binding.propertyName?.text ?? name };
  }
}
function declaration(sf: ts.SourceFile, name: string): ts.Node | undefined {
  let result: ts.Node | undefined;
  const visit = (node: ts.Node) => {
    if ((ts.isVariableDeclaration(node) || ts.isFunctionDeclaration(node) || ts.isTypeAliasDeclaration(node) || ts.isInterfaceDeclaration(node))
      && node.name?.getText() === name) result ??= node;
    ts.forEachChild(node, visit);
  };
  visit(sf); return result;
}
function text(node: ts.Node, sf: ts.SourceFile, env = new Map<string, string>(), depth = 0): string {
  if (depth > 12) throw new Error("D12 recursive client path");
  if (ts.isParenthesizedExpression(node) || ts.isAsExpression(node)) return text(node.expression, sf, env, depth + 1);
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (ts.isTemplateExpression(node)) return node.head.text + node.templateSpans.map(span => text(span.expression, sf, env, depth + 1) + span.literal.text).join("");
  // Optional pagination query strings are not part of the endpoint path.
  if (ts.isConditionalExpression(node) && (ts.isStringLiteral(node.whenFalse) || ts.isNoSubstitutionTemplateLiteral(node.whenFalse))
    && node.whenFalse.text === "" && /[?]/.test(node.whenTrue.getText())) return "";
  if (ts.isIdentifier(node)) {
    if (env.has(node.text)) return env.get(node.text)!;
    const value = declaration(sf, node.text);
    return value && ts.isVariableDeclaration(value) && value.initializer ? text(value.initializer, sf, env, depth + 1) : PARAM;
  }
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken)
    return text(node.left, sf, env, depth + 1) + text(node.right, sf, env, depth + 1);
  if (ts.isCallExpression(node)) {
    if (ts.isPropertyAccessExpression(node.expression) && node.expression.name.text === "replace" && node.arguments.length === 2
      && ts.isStringLiteral(node.arguments[0])) return text(node.expression.expression, sf, env, depth + 1)
        .replace(node.arguments[0].text, text(node.arguments[1], sf, env, depth + 1));
    if (node.expression.getText() === "encodeURIComponent") return text(node.arguments[0], sf, env, depth + 1);
    const fn = declaration(sf, node.expression.getText());
    const callable = fn && ts.isVariableDeclaration(fn) && fn.initializer && ts.isArrowFunction(fn.initializer) ? fn.initializer : fn;
    if (callable && (ts.isFunctionDeclaration(callable) || ts.isArrowFunction(callable)) && callable.body) {
      const returned = ts.isBlock(callable.body) ? callable.body.statements.find(ts.isReturnStatement)?.expression : callable.body;
      if (returned) return text(returned, sf, new Map(callable.parameters.map((p, i) => [p.name.getText(),
        node.arguments[i] ? text(node.arguments[i], sf, env, depth + 1) : PARAM])), depth + 1);
    }
  }
  return PARAM;
}
// The OpenAPI JSONField schema intentionally leaves some values unconstrained.
// Read the actual client's explicit response type for those holes. Never infer a
// domain choice, call application code, or change a declared OpenAPI constraint.
function witness(node: ts.TypeNode, sf: ts.SourceFile, depth = 0): unknown {
  if (depth > 18) return undefined;
  if (ts.isParenthesizedTypeNode(node)) return witness(node.type, sf, depth + 1);
  if (ts.isArrayTypeNode(node) || ts.isTupleTypeNode(node)) return [];
  if (ts.isTypeOperatorNode(node)) return witness(node.type, sf, depth + 1);
  if (ts.isUnionTypeNode(node)) {
    if (node.types.some(type => type.kind === ts.SyntaxKind.NullKeyword || ts.isLiteralTypeNode(type) && type.literal.kind === ts.SyntaxKind.NullKeyword)) return null;
    return node.types.map(type => witness(type, sf, depth + 1)).find(value => value !== undefined);
  }
  if (ts.isIntersectionTypeNode(node)) return Object.assign({}, ...node.types.map(type => witness(type, sf, depth + 1)));
  if (ts.isTypeLiteralNode(node)) return Object.fromEntries(node.members.flatMap(member => {
    // Optional declared fields may be present too. In particular bookings?:
    // {upcoming,past} is a valid object, whereas {} crashes the real consumer.
    if (!ts.isPropertySignature(member) || !member.type) return [];
    const value = witness(member.type, sf, depth + 1);
    return value === undefined ? [] : [[member.name.getText().replace(/^["']|["']$/g, ""), value]];
  }));
  if (ts.isTypeReferenceNode(node)) {
    const name = node.typeName.getText();
    if (["Array", "ReadonlyArray"].includes(name)) return [];
    if (name === "Record") return {};
    const local = declaration(sf, name);
    if (local && ts.isTypeAliasDeclaration(local)) return witness(local.type, sf, depth + 1);
    if (local && ts.isInterfaceDeclaration(local)) return witness(ts.factory.createTypeLiteralNode(local.members), sf, depth + 1);
    const binding = imported(sf, name);
    const target = binding && declaration(binding.file, binding.name);
    if (binding && target && ts.isTypeAliasDeclaration(target)) return witness(target.type, binding.file, depth + 1);
    if (binding && target && ts.isInterfaceDeclaration(target)) return witness(ts.factory.createTypeLiteralNode(target.members), binding.file, depth + 1);
  }
  if (ts.isLiteralTypeNode(node)) {
    if (ts.isStringLiteral(node.literal)) return node.literal.text;
    if (ts.isNumericLiteral(node.literal)) return Number(node.literal.text);
    if (node.literal.kind === ts.SyntaxKind.FalseKeyword) return false;
    if (node.literal.kind === ts.SyntaxKind.TrueKeyword) return true;
  }
  if (node.kind === ts.SyntaxKind.StringKeyword) return "";
  if (node.kind === ts.SyntaxKind.NumberKeyword) return 0;
  if (node.kind === ts.SyntaxKind.BooleanKeyword) return false;
  return undefined;
}
for (const file of sourceFiles()) {
  const sf = source(file);
  const visit = (node: ts.Node) => {
    if (ts.isCallExpression(node) && /^(apiGet|memberRequest|staffRequest|publicV1Request|tenantPublicRequest)$/.test(node.expression.getText()) && node.typeArguments?.length) {
      const argument = node.arguments[node.expression.getText() === "tenantPublicRequest" ? 1 : 0];
      const pattern = argument && text(argument, sf).split("?")[0].replace(/\/$/, "");
      if (pattern?.startsWith("/") && pattern.split(PARAM).join("").length > 5) candidates.push({
        match: new RegExp(`^${pattern.replace(/[.*+?^$()|[\]\\]/g, "\\$&").split(PARAM).join("[^/]+")}$`),
        weight: pattern.split(PARAM).join("").length, type: node.typeArguments[0], file: sf,
      });
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
}
candidates.sort((a, b) => b.weight - a.weight);
export function declaredClientPage(path: string) {
  return candidates.some(candidate => {
    if (!candidate.match.test(path)) return false;
    const shape = witness(candidate.type, candidate.file) as Record<string, unknown> | undefined;
    return shape && typeof shape === "object" && !Array.isArray(shape) && ["count", "next", "previous", "results"].every(key => key in shape)
      && Array.isArray(shape.results);
  });
}
const shapes = new Map<string, unknown>();
export function opaqueClientField(key: string): unknown {
  const [path, ...fields] = key.split(".");
  if (!shapes.has(path)) {
    const candidate = candidates.find(item => item.match.test(path));
    shapes.set(path, candidate ? witness(candidate.type, candidate.file) : undefined);
  }
  let value = shapes.get(path);
  for (const field of fields) value = value && typeof value === "object" ? (value as Record<string, unknown>)[field] : undefined;
  return value;
}
