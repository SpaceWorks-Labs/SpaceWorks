// The user-facing positions the frontend literal guard checks (phase 8 i18n).
//
// A literal counts as user-facing copy when it is prose (see `isProse`) AND sits in one of
// these positions: JSX text; a display attribute (`aria-label`, `alt`, `title`,
// `placeholder`, `label`, ...); a string rendered as a JSX child; a display property of an
// object (`label: "..."`); a value of a copy map (`const STATUS_LABELS = {...}`, or any object
// literal typed `Record<string, string>` whatever its name); a toast,
// confirm, alert or `new Error(...)` message; a message setter (`setError("...")`); or a
// return value of a function named like a label (`statusLabel`, `emptyText`, ...); or the
// default of a display prop (`{ title = "..." }`).
// Copy inside `t`/`msg`/`plural`/`select` or a `<Trans>` element is marked. A reviewed
// technical exception carries `i18n-ignore: <reason>` on its line or the line above.
import ts from "typescript";

export const DISPLAY_ATTRIBUTE = /^(aria-(label|description|placeholder|roledescription|valuetext)|alt|title|placeholder|label|description|hint|helpText|helperText|heading|subheading|subtitle|caption|eyebrow|kicker|message|tooltip|summary|lede|emptyText|emptyLabel|emptyMessage|emptyTitle|emptyDescription|confirmLabel|cancelLabel|submitLabel|actionLabel|loadingLabel|successMessage|errorMessage|helper|body|intro|footnote|legend|prompt)$/;
export const DISPLAY_PROPERTY = /^(label|header|title|description|placeholder|hint|helpText|helperText|heading|subheading|subtitle|caption|eyebrow|message|tooltip|summary|lede|emptyText|emptyLabel|emptyMessage|emptyTitle|emptyDescription|confirmLabel|cancelLabel|submitLabel|actionLabel|ariaLabel|successMessage|errorMessage|body|text|blurb|note|detail|reason|question|answer|cta|helper|error|intro|prompt)$/;
export const COPY_MAP = /(LABELS?|COPY|TEXTS?|MESSAGES?|TITLES?|DESCRIPTIONS?|HINTS?|NAMES|HEADINGS?|BLURBS?|CAPTIONS?|Labels|Copy|Messages|Titles|Descriptions|Hints|Names)$/;
export const LABEL_FUNCTION = /(Label|Text|Message|Title|Description|Copy|Hint|Caption|Summary|Heading|Error|Reason|Notice|Blurb|Sentence|Phrase|Explanation|Status|Wording)$/;
export const MESSAGE_SETTER = /^set\w*(Error|Message|Notice|Status|Feedback|Hint|Toast|Copy|Warning|Info|Problem|Text)$/;
export const TOAST_CALL = /^(toast|showToast|pushToast|notify|confirm|alert)$/;
const MARKER_TAGS = new Set(["t", "msg", "defineMessage"]);
const MARKER_CALLS = new Set(["t", "msg", "plural", "select", "selectOrdinal", "defineMessage", "_"]);
const IGNORE = "i18n-ignore:";

/** Prose: a letter, plus a space, a capital start or closing punctuation. Codes, CSS, paths are not. */
export function isProse(text) {
  const value = text.trim();
  if (!/[A-Za-z]/.test(value)) return false;
  if (/^(https?:|mailto:|tel:|\/|#|\.|@)/.test(value)) return false;
  if (/^[a-z0-9_.:/#@-]+$/.test(value)) return false;
  if (/^[a-z][a-zA-Z0-9]*$/.test(value)) return false;
  if (/^[A-Z0-9_]{2,}$/.test(value) && value.length <= 4 && !/^(OK|NO|YES)$/.test(value)) return false;
  const tokens = value.split(/\s+/);
  if (tokens.every((token) => /^[a-z0-9:/[\]._%!-]+$/.test(token)) && tokens.some((token) => token.includes("-"))) return false;
  return /\s/.test(value) || /^[A-Z]/.test(value) || /[.?!:…]$/.test(value);
}

function name(node) {
  if (!node) return "";
  if (ts.isIdentifier(node) || ts.isPrivateIdentifier(node)) return node.text;
  if (ts.isStringLiteral(node)) return node.text;
  if (ts.isPropertyAccessExpression(node)) return node.name.text;
  return "";
}

export function isMarked(node) {
  for (let current = node.parent; current && !ts.isSourceFile(current); current = current.parent) {
    if (ts.isTaggedTemplateExpression(current) && MARKER_TAGS.has(name(current.tag))) return true;
    if (ts.isCallExpression(current) && MARKER_CALLS.has(name(current.expression))) return true;
    if (ts.isJsxElement(current) && name(current.openingElement.tagName) === "Trans") return true;
  }
  return false;
}

const lineCache = new WeakMap();

export function isIgnored(sourceFile, node) {
  if (!lineCache.has(sourceFile)) lineCache.set(sourceFile, sourceFile.text.split(/\r?\n/));
  const lines = lineCache.get(sourceFile);
  const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
  return [line, line - 1].some((index) => index >= 0 && (lines[index] ?? "").includes(IGNORE));
}

/** The prose string/template literals a display expression renders. */
export function proseLiterals(expr) {
  if (!expr) return [];
  if (ts.isParenthesizedExpression(expr) || ts.isAsExpression(expr) || ts.isSatisfiesExpression?.(expr)) return proseLiterals(expr.expression);
  if (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) return isProse(expr.text) ? [expr] : [];
  if (ts.isTemplateExpression(expr)) {
    const text = [expr.head.text, ...expr.templateSpans.map((span) => span.literal.text)].join(" ");
    return isProse(text) ? [expr] : [];
  }
  if (ts.isConditionalExpression(expr)) return [...proseLiterals(expr.whenTrue), ...proseLiterals(expr.whenFalse)];
  if (ts.isBinaryExpression(expr) && [ts.SyntaxKind.BarBarToken, ts.SyntaxKind.QuestionQuestionToken, ts.SyntaxKind.AmpersandAmpersandToken].includes(expr.operatorToken.kind)) {
    return [...(expr.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken ? [] : proseLiterals(expr.left)), ...proseLiterals(expr.right)];
  }
  return [];
}

function enclosingFunctionName(node) {
  for (let current = node.parent; current; current = current.parent) {
    if (ts.isFunctionDeclaration(current) || ts.isMethodDeclaration(current)) return name(current.name);
    if (ts.isArrowFunction(current) || ts.isFunctionExpression(current)) {
      const parent = current.parent;
      if (parent && ts.isVariableDeclaration(parent)) return name(parent.name);
      if (parent && ts.isPropertyAssignment(parent)) return name(parent.name);
      return "";
    }
  }
  return "";
}

const isStringRecordType = (type) => Boolean(type) && ts.isTypeReferenceNode(type) && name(type.typeName) === "Record"
  && type.typeArguments?.length === 2 && type.typeArguments.every((arg) => arg.kind === ts.SyntaxKind.StringKeyword);

/** An object literal typed `Record<string, string>` (annotation, `as`, or a lazy `(): Record<...> => ({...})`) is a lookup map of display words. */
function isStringRecordMap(property) {
  const object = property.parent;
  if (!object || !ts.isObjectLiteralExpression(object)) return false;
  let holder = object.parent;
  while (holder && ts.isParenthesizedExpression(holder)) holder = holder.parent;
  if (holder && (ts.isAsExpression(holder) || ts.isSatisfiesExpression?.(holder))) return isStringRecordType(holder.type);
  if (holder && ts.isArrowFunction(holder)) return isStringRecordType(holder.type);
  return Boolean(holder && ts.isVariableDeclaration(holder) && isStringRecordType(holder.type));
}

function copyMapName(node) {
  for (let current = node.parent; current; current = current.parent) {
    if (ts.isVariableDeclaration(current)) return name(current.name);
    if (ts.isFunctionLike(current) || ts.isSourceFile(current)) return "";
  }
  return "";
}

/**
 * Visit every display position in a file: `onText(jsxText)` for JSX text and
 * `onLiteral(literal, category)` for string/template literals.
 */
export function visitPositions(sourceFile, { onText, onLiteral }) {
  const literal = (expr, category) => proseLiterals(expr).forEach((node) => onLiteral(node, category));
  const visit = (node) => {
    if (ts.isJsxText(node)) {
      if (isProse(node.text)) onText(node);
    } else if (ts.isJsxAttribute(node) && node.initializer && DISPLAY_ATTRIBUTE.test(name(node.name))) {
      literal(ts.isJsxExpression(node.initializer) ? node.initializer.expression : node.initializer, "attribute");
    } else if (ts.isJsxExpression(node) && node.expression && (ts.isJsxElement(node.parent) || ts.isJsxFragment(node.parent))) {
      literal(node.expression, "jsx-child");
    } else if (ts.isBindingElement(node) && node.initializer && DISPLAY_PROPERTY.test(name(node.propertyName ?? node.name))) {
      literal(node.initializer, "default-prop");
    } else if (ts.isPropertyAssignment(node)) {
      if (DISPLAY_PROPERTY.test(name(node.name))) literal(node.initializer, "property");
      else if (COPY_MAP.test(copyMapName(node)) || isStringRecordMap(node)) literal(node.initializer, "copy-map");
    } else if (ts.isArrayLiteralExpression(node) && COPY_MAP.test(copyMapName(node)) && ts.isVariableDeclaration(node.parent)) {
      node.elements.forEach((element) => literal(element, "copy-map"));
    } else if (ts.isNewExpression(node) && name(node.expression) === "Error" && node.arguments?.length) {
      literal(node.arguments[0], "error");
    } else if (ts.isCallExpression(node) && node.arguments.length) {
      const callee = name(node.expression);
      const owner = ts.isPropertyAccessExpression(node.expression) ? name(node.expression.expression) : "";
      if (TOAST_CALL.test(callee) || owner === "toast" || MESSAGE_SETTER.test(callee)) literal(node.arguments[0], "message");
    } else if (ts.isReturnStatement(node) && node.expression && LABEL_FUNCTION.test(enclosingFunctionName(node))) {
      literal(node.expression, "label-function");
    } else if (ts.isArrowFunction(node) && !ts.isBlock(node.body) && LABEL_FUNCTION.test(enclosingFunctionName(node.body))) {
      literal(node.body, "label-function");
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
}

/** Findings for one file: `[{ line, category }]` of unmarked, unignored copy. */
export function findUnmarked(sourceFile) {
  const findings = [];
  const add = (node, category) => {
    if (isMarked(node) || isIgnored(sourceFile, node)) return;
    findings.push({ line: sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1, category });
  };
  visitPositions(sourceFile, { onText: (node) => add(node, "jsx-text"), onLiteral: add });
  return findings;
}
