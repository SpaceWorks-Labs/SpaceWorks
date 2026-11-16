import ts from "typescript";
import { expect, it } from "vitest";
// @ts-expect-error The production literal guard is JavaScript without declarations.
import { findUnmarked } from "../../../scripts/i18n-literal-positions.mjs";
const scan = (body: string) => findUnmarked(ts.createSourceFile("sample.tsx", body, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX));

it.each(["{number}, {kind}", "{number}, {kind}, {amount}, {currency}, {due_on}"])(
  "keeps the identifier-only code sample %s literal", text => {
    expect(scan('const Example = () => <code>{' + JSON.stringify(text) + '}</code>;')).toEqual([]);
  },
);
it.each([
  '<code>{"Use {number}, {kind}"}</code>',
  '<code>{"{number}, pay now"}</code>',
  '<code>{"Invoice amount"}</code>',
  '<p>{"{number}, {kind}"}</p>',
  '<code aria-label="{number}, {kind}" />',
  '<code>{"{number}, {kind}."}</code>',
])("still rejects display prose or non-code positions: %s", jsx => {
  const findings = scan("const Example = () => " + jsx + ";");
  expect(findings).toHaveLength(1);
  expect(findings[0].category).toBe(jsx.includes("aria-label") ? "attribute" : "jsx-child");
});
