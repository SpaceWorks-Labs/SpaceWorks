import { describe, expect, it } from "vitest";
import { linkMarkdown, linkTargetOk, prefixLines, wrapSelection } from "./markdownEdit";

describe("broadcast toolbar edits", () => {
  it("wraps and unwraps a selection", () => {
    const on = wrapSelection("Say hello", 4, 9, "**", "bold");
    expect(on).toEqual({ text: "Say **hello**", start: 6, end: 11 });
    expect(wrapSelection(on.text, on.start, on.end, "**", "bold").text).toBe("Say hello");
  });
  it("numbers every selected line and removes the prefix when applied again", () => {
    const listed = prefixLines("Bring\nYour badge", 0, 15, "1. ");
    expect(listed.text).toBe("1. Bring\n2. Your badge");
    expect(prefixLines(listed.text, 0, listed.text.length, "1. ").text).toBe("Bring\nYour badge");
    expect(prefixLines("- Item", 0, 6, "## ").text).toBe("## Item");
  });
  it("accepts only https, mailto and link placeholders", () => {
    expect(linkTargetOk("https://example.org/a")).toBe(true);
    expect(linkTargetOk("mailto:desk@example.org")).toBe(true);
    expect(linkTargetOk("{{ ticket_url }}")).toBe(true);
    expect(linkTargetOk("javascript:void(0)")).toBe(false);
    expect(linkTargetOk("http://example.org")).toBe(false);
    expect(linkMarkdown("See [the] map", "https://x.org")).toBe("[See the map](https://x.org)");
  });
});
