import { describe, expect, it } from "vitest";
import { markdownExcerpt, markdownInlineTokens } from "./restrictedMarkdownTokens";

const hasLink = (input: string) => markdownInlineTokens(input).some(token => token.kind === "link");

describe("markdownInlineTokens", () => {
  it("returns plain text as a single text token", () => expect(markdownInlineTokens("hello")).toEqual([{ kind: "text", text: "hello" }]));
  it("returns nothing for empty input", () => expect(markdownInlineTokens("")).toEqual([]));
  it("splits bold from the surrounding text", () => expect(markdownInlineTokens("a **b** c")).toEqual([
    { kind: "text", text: "a " }, { kind: "strong", text: "b" }, { kind: "text", text: " c" }]));
  it("keeps unclosed or empty bold markers literal", () => {
    expect(markdownInlineTokens("a **b")).toEqual([{ kind: "text", text: "a **b" }]);
    expect(markdownInlineTokens("****")).toEqual([{ kind: "text", text: "****" }]);
  });
  it("refuses bold that spans a newline", () => expect(markdownInlineTokens("**a\nb**")).toEqual([{ kind: "text", text: "**a\nb**" }]));
  it("makes a link from an http(s) target", () => expect(markdownInlineTokens("see [docs](https://example.org/a) now")).toEqual([
    { kind: "text", text: "see " }, { kind: "link", text: "docs", url: "https://example.org/a" }, { kind: "text", text: " now" }]));
  it("allows balanced parentheses inside a link target", () => expect(markdownInlineTokens("[w](https://e.org/a_(b))")).toEqual([
    { kind: "link", text: "w", url: "https://e.org/a_(b)" }]));
  it.each([
    ["a javascript scheme", "[x](javascript:alert(1))"],
    ["a data scheme", "[x](data:text/html,hi)"],
    ["credentials in the URL", "[x](https://user:pw@example.org/)"],
    ["control characters via encoding", "[x](https://example.org/%00)"],
    ["an unclosed target", "[x](https://example.org/a"],
    ["an empty label", "[](https://example.org/)"],
    ["a label with brackets", "[a[b]](https://example.org/)"],
    ["an image marker", "![x](https://example.org/i.png)"],
    ["a malformed URL", "[x](https://)"],
  ])("never links %s", (_name, input) => expect(hasLink(input)).toBe(false));
  it("refuses a target longer than 500 characters", () => expect(hasLink(`[x](https://example.org/${"a".repeat(600)})`)).toBe(false));
  it("refuses a label longer than 200 characters", () => expect(hasLink(`[${"a".repeat(201)}](https://example.org/)`)).toBe(false));
  it("refuses a target nested deeper than 8 parentheses", () => expect(hasLink(`[x](https://e.org/${"(".repeat(9)}${")".repeat(9)})`)).toBe(false));
});

describe("markdownExcerpt", () => {
  it("strips markup and list dashes and collapses whitespace", () => expect(markdownExcerpt("- **Bold**\n- [a](https://e.org/)  more")).toBe("Bold a more"));
  it("keeps legacy literal text untouched apart from whitespace", () => expect(markdownExcerpt("- **Bold**\n\nx", "legacy_literal")).toBe("- **Bold** x"));
  it("caps the excerpt at 300 characters", () => expect(markdownExcerpt("a".repeat(400))).toHaveLength(300));
});
