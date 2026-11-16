import { describe, expect, it } from "vitest";
import * as ts from "typescript";

// Raw source enumeration avoids importing product modules or starting providers.
const sources = import.meta.glob<string>("/src/**/*.{ts,tsx}", {
  query: "?raw", import: "default", eager: true,
});
type Sink = { key: string; path: string; kind: string; node: ts.Node; source: ts.SourceFile };
const sinks: Sink[] = [];
for (const [path, text] of Object.entries(sources)) {
  if (/\.(?:test|spec)\.[cm]?[jt]sx?$/.test(path) || /\/(?:__tests__|test)\//.test(path)) continue;
  const source = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true,
    path.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const counts = new Map<string, number>();
  const add = (kind: string, node: ts.Node) => {
    const index = counts.get(kind) ?? 0;
    counts.set(kind, index + 1);
    sinks.push({ key: `${path}#${kind}#${index}`, path, kind, node, source });
  };
  const walk = (node: ts.Node) => {
    if (ts.isJsxAttribute(node) && ["dangerouslySetInnerHTML", "srcDoc"].includes(node.name.getText(source))) {
      add(node.name.getText(source), node);
    }
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken
      && ts.isPropertyAccessExpression(node.left) && ["innerHTML", "outerHTML"].includes(node.left.name.text)) {
      add(node.left.name.text, node);
    }
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
      && ["parseFromString", "insertAdjacentHTML", "write", "writeln", "createContextualFragment", "setHTMLUnsafe"].includes(node.expression.name.text)) {
      // write/writeln on another object remains conservative and needs a case.
      add(node.expression.name.text, node);
    }
    ts.forEachChild(node, walk);
  };
  walk(source);
}

const CASES: Record<string, string> = {
  "/src/components/LogoLoader.tsx#dangerouslySetInnerHTML#0": "constant-logo",
  "/src/components/BoxSpinner.tsx#dangerouslySetInnerHTML#0": "constant-logo",
  "/src/components/brand/LogoBoxOverlay.tsx#dangerouslySetInnerHTML#0": "constant-logo",
  "/src/features/docs/MermaidDiagram.tsx#dangerouslySetInnerHTML#0": "strict-mermaid",
  "/src/features/docs/MermaidDiagram.tsx#dangerouslySetInnerHTML#1": "strict-mermaid",
  "/src/features/staff/eventProgramme/BroadcastDeliveryControls.tsx#srcDoc#0": "broadcast-sandbox",
  "/src/features/staff/panels/EmailTemplateEditorParts.tsx#srcDoc#0": "email-sandbox",
  "/src/features/events/hackathonSubmissions/AssetPreview.tsx#parseFromString#0": "strict-svg",
  "/src/features/staff/panels/machine/filePreview/svgFile.ts#parseFromString#0": "sanitized-svg",
};
// A new exemption requires an exact sink ID and a reviewable one-line reason.
const EXEMPTIONS: Record<string, string> = {
  "/src/features/spaceDisplay/useDisplayScreen.ts#write#0": "store.write persists a registration token through the token-store adapter; it does not render HTML.",
  "/src/features/spaceDisplay/useDisplayScreen.ts#write#1": "store.write clears the token-store adapter with null; it does not render HTML.",
};

describe("D09 product rendering sink census", () => {
  it("joins every source sink to a case, detecting additions and stale allowances", () => {
    expect(sinks.map(sink => sink.key).sort()).toEqual([...Object.keys(CASES), ...Object.keys(EXEMPTIONS)].sort());
    expect(new Set(sinks.map(sink => sink.key)).size).toBe(sinks.length);
    expect(Object.keys(CASES).filter(key => key in EXEMPTIONS)).toEqual([]);
    for (const reason of Object.values(EXEMPTIONS)) expect(reason.trim() !== "" && !reason.includes("\n")).toBe(true);
  });

  it.each(sinks)("pins the reviewed safety boundary for $key", sink => {
    if (sink.key in EXEMPTIONS) {
      expect((sink.node as ts.CallExpression).expression.getText(sink.source)).toBe("store.write");
      return;
    }
    const policy = CASES[sink.key];
    expect(policy, sink.key).toBeDefined();
    if (policy === "constant-logo") {
      expect(sink.node.getText(sink.source)).toBe("dangerouslySetInnerHTML={{ __html: BOX }}");
      const imports = sink.source.statements.filter(ts.isImportDeclaration);
      const box = imports.filter(node => node.importClause?.namedBindings
        && ts.isNamedImports(node.importClause.namedBindings)
        && node.importClause.namedBindings.elements.some(item => item.name.text === "BOX"));
      expect(box).toHaveLength(1);
      expect((box[0].moduleSpecifier as ts.StringLiteral).text).toMatch(/(?:\.\/|\.\.\/)boxOpen\/shared$/);
    } else if (policy === "email-sandbox" || policy === "broadcast-sandbox") {
      const element = sink.node.parent as ts.JsxAttributes;
      const sandbox = element.properties.find(item => ts.isJsxAttribute(item) && item.name.getText(sink.source) === "sandbox");
      expect(sandbox && ts.isJsxAttribute(sandbox) && sandbox.initializer && ts.isStringLiteral(sandbox.initializer)
        ? sandbox.initializer.text : undefined).toBe(policy === "email-sandbox" ? "" : "allow-same-origin");
    } else if (policy === "strict-mermaid") {
      const settings: ts.PropertyAssignment[] = [];
      const walk = (node: ts.Node) => {
        if (ts.isPropertyAssignment(node) && node.name.getText(sink.source) === "securityLevel") settings.push(node);
        ts.forEachChild(node, walk);
      };
      walk(sink.source);
      expect(settings).toHaveLength(1);
      expect(settings[0].initializer.getText(sink.source)).toBe('"strict"');
    } else {
      expect(["strict-svg", "sanitized-svg"]).toContain(policy);
      expect(sink.node.getText(sink.source)).toMatch(/\.parseFromString\((value|text), "image\/svg\+xml"\)/);
    }
  });
});
