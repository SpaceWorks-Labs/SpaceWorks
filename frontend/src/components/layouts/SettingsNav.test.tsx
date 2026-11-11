import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { SettingsNav } from "./SettingsNav";

afterEach(() => vi.unstubAllGlobals());
function viewport(width: number) {
  vi.stubGlobal("matchMedia", (query: string) => {
    const min = Number(query.match(/min-width: (\d+)px/)?.[1] ?? 0);
    const max = Number(query.match(/max-width: (\d+)px/)?.[1] ?? Infinity);
    return { matches: width >= min && width <= max, addEventListener: vi.fn(), removeEventListener: vi.fn() };
  });
}
const sections = [{ id: "profile", title: "Profile" }, { id: "billing", title: "Billing" }];

it("collapses to one native select on phones that jumps to and focuses the section", () => {
  viewport(375);
  render(<><SettingsNav sections={sections} /><div id="billing" tabIndex={-1}>Billing rows</div></>);
  const nav = screen.getByRole("navigation", { name: "Settings sections" });
  expect(nav).toHaveClass("sw-settings-nav");
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Jump to section" }), { target: { value: "billing" } });
  expect(screen.getByText("Billing rows")).toHaveFocus();
});

it("keeps the link rail from tablet up", () => {
  viewport(1024);
  render(<SettingsNav sections={sections} />);
  expect(screen.getAllByRole("link")).toHaveLength(2);
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
});
