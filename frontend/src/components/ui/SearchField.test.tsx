import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it, vi } from "vitest";
import { SearchField, searchItemStyle } from "./SearchField";
import { expectNoA11yViolations } from "../../test/axe";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const css = readFileSync(join(process.cwd(), "src/components/ui/SearchField.css"), "utf8");

function Controlled(props: { onChange?: (value: string) => void; loading?: boolean; shortcut?: string; clearOnEscape?: boolean }) {
  const [value, setValue] = useState("");
  return <SearchField aria-label="Find tools" value={value} loading={props.loading} shortcut={props.shortcut} clearOnEscape={props.clearOnEscape}
    onChange={event => { setValue(event.target.value); props.onChange?.(event.target.value); }} />;
}

it("is a labelled searchbox and stays accessible", async () => {
  const { container } = render(<Controlled shortcut="Ctrl K" />);
  expect(screen.getByRole("searchbox", { name: "Find tools" })).toHaveAttribute("type", "search");
  await expectNoA11yViolations(container);
});

it("shows the clear button only with text, clears through the call site's onChange and keeps focus", () => {
  const seen: string[] = [];
  render(<Controlled onChange={value => seen.push(value)} />);
  const input = screen.getByRole("searchbox") as HTMLInputElement;
  expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull();
  fireEvent.change(input, { target: { value: "drill" } });
  fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
  expect(seen).toEqual(["drill", ""]);
  expect(input.value).toBe("");
  expect(input).toHaveFocus();
  expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull();
});

it("clears on Escape without bubbling, and leaves an empty field's Escape alone", () => {
  const outer = vi.fn();
  render(<div onKeyDown={outer}><Controlled /></div>);
  const input = screen.getByRole("searchbox") as HTMLInputElement;
  fireEvent.keyDown(input, { key: "Escape" });
  expect(outer).toHaveBeenCalledTimes(1);
  fireEvent.change(input, { target: { value: "saw" } });
  fireEvent.keyDown(input, { key: "Escape" });
  expect(input.value).toBe("");
  expect(outer).toHaveBeenCalledTimes(1);
  expect(input).toHaveFocus();
});

it("lets Escape through when clearOnEscape is off", () => {
  const outer = vi.fn();
  render(<div onKeyDown={outer}><Controlled clearOnEscape={false} /></div>);
  const input = screen.getByRole("searchbox") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "saw" } });
  fireEvent.keyDown(input, { key: "Escape" });
  expect(input.value).toBe("saw");
  expect(outer).toHaveBeenCalledTimes(1);
});

it("swaps the magnifier for the box-open spinner while loading", () => {
  const { container, rerender } = render(<SearchField aria-label="Find" />);
  expect(screen.queryByRole("status")).toBeNull();
  expect(container.querySelector(".sw-search-icon")).not.toHaveAttribute("data-loading");
  rerender(<SearchField aria-label="Find" loading />);
  expect(screen.getByRole("status", { name: "Searching…" })).toBeInTheDocument();
  expect(container.querySelector(".sw-search-icon")).toHaveAttribute("data-loading");
  rerender(<SearchField aria-label="Find" loading={false} />);
  expect(screen.queryByRole("status")).toBeNull();
});

it("works uncontrolled and moves layout classes to the wrapper", () => {
  const { container } = render(<SearchField aria-label="Find" defaultValue="abc" className="desk-input min-h-11 flex-1 sm:max-w-sm pl-9" />);
  const input = screen.getByRole("searchbox");
  expect(input.className).toContain("min-h-11");
  expect(input.className).not.toContain("flex-1");
  expect(input.className).not.toContain("pl-9");
  expect(container.querySelector(".sw-search")).toHaveClass("flex-1", "sm:max-w-sm");
  fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
  expect((input as HTMLInputElement).value).toBe("");
});

it("never shows clear on a disabled field and hides the shortcut chip from assistive tech", () => {
  render(<SearchField aria-label="Find" defaultValue="x" disabled shortcut="Ctrl K" />);
  expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull();
  expect(screen.getByText("Ctrl K")).toHaveAttribute("aria-hidden", "true");
});

it("css: focus eases colour and nudges 2px, reduced motion drops movement, tokens only", () => {
  expect(css).toMatch(/\.sw-search:focus-within \.sw-search-glyph \{ transform: translateX\(2px\)/);
  expect(css).toMatch(/\.sw-search:focus-within \.sw-search-kbd/);
  expect(css).toMatch(/scale\(0\.9\)/);
  expect(css).toMatch(/translateY\(4px\)/);
  expect(css).toMatch(/calc\(var\(--sw-i, 0\) \* 20ms\)/);
  const reduced = css.slice(css.indexOf("prefers-reduced-motion"));
  expect(reduced).toMatch(/translateX|transform: none/);
  expect(reduced).not.toMatch(/scale\(0\.9\)|translateY/);
  expect(css).not.toMatch(/#[0-9a-fA-F]{3,6}\b|rgba?\(\d/);
});

it("staggers only the first six rows", () => {
  expect(searchItemStyle(0)).toEqual({ "--sw-i": 0 });
  expect(searchItemStyle(9)).toEqual({ "--sw-i": 5 });
});
