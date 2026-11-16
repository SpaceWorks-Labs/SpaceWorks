import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { PublicHeader } from "./PublicHeader";

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
function viewport(width: number) {
  vi.stubGlobal("matchMedia", (query: string) => {
    const min = Number(query.match(/min-width: (\d+)px/)?.[1] ?? 0);
    const max = Number(query.match(/max-width: (\d+)px/)?.[1] ?? Infinity);
    return { matches: width >= min && width <= max, addEventListener: vi.fn(), removeEventListener: vi.fn() };
  });
}
const nav = [{ label: "Catalogue", href: "/m/lab" }, { label: "Events", href: "/m/lab/events" }, { label: "Book a space", href: "/m/lab/bookings" }];
const name = "Alpha Robotics Lab and Community Fabrication Workshop";
const header = () => render(<PublicHeader makerspace={{ name, slug: "lab" }} nav={nav}
  account={{ label: "Sign in", href: "/m/lab/member" }} liveStatus={<span>Main Campus · Room A12</span>} />);

describe("PublicHeader", () => {
  it.each(["/m/lab", "/"])("replaces the default header identity with the uploaded tenant logo at %s", async homeHref => {
    viewport(390);
    const { container } = render(<PublicHeader makerspace={{ name: "Tinkerspace", slug: "lab", logo: "/public-images/lab/logo.webp", homeHref }}
      nav={[]} account={{ label: "Sign in", href: "/member" }} />);
    const home = screen.getByRole("link", { name: "Tinkerspace home" });
    expect(home).toHaveAttribute("href", homeHref);
    const logo = within(home).getByRole("img", { name: "Tinkerspace" });
    expect(logo).toHaveAttribute("src", "/public-images/lab/logo.webp");
    expect(logo).toHaveClass("object-contain", "w-auto");
    expect(within(home).queryByText("Tinkerspace")).toBeNull();
    expect(home.querySelector("[data-logo]")).toBeNull();
    await expectNoA11yViolations(container);
  });

  it.each(["/m/lab", "/"])("keeps the Space Works mark and makerspace name without an uploaded logo at %s", async homeHref => {
    viewport(1440);
    const { container } = render(<PublicHeader makerspace={{ name: "Tinkerspace", slug: "lab", homeHref }}
      nav={[]} account={{ label: "Sign in", href: "/member" }} />);
    const home = screen.getByRole("link", { name: "Tinkerspace home" });
    expect(home).toHaveAttribute("href", homeHref);
    expect(within(home).getByText("Tinkerspace")).toBeVisible();
    expect(home.querySelector('[data-logo="symbol"]')).toBeInTheDocument();
    expect(home.querySelector("img")).toBeNull();
    await expectNoA11yViolations(container);
  });

  it("keeps links inline on desktop with the account action last and the full name available", async () => {
    viewport(1990);
    const { container } = header();
    const links = within(screen.getByRole("navigation", { name: "Public navigation" })).getAllByRole("link");
    expect(links.map(link => link.textContent)).toEqual(["Catalogue", "Events", "Book a space"]);
    expect(screen.queryByRole("button", { name: "Menu" })).not.toBeInTheDocument();
    expect(screen.getByText("Main Campus · Room A12")).toBeInTheDocument();
    expect(screen.getByTitle(name)).toHaveClass("line-clamp-2");
    const all: HTMLElement[] = Array.from(container.querySelectorAll("a"));
    expect(all.at(-1)).toHaveTextContent("Sign in");
    expect(all.indexOf(screen.getByRole("link", { name: "Sign in" }))).toBeGreaterThan(all.indexOf(links[2]));
    await expectNoA11yViolations(container);
  });
  it.each([375, 820])("moves links and status into a menu at %ipx, leaving sign-in visible", async width => {
    viewport(width);
    const { container } = header();
    expect(screen.queryByRole("navigation", { name: "Public navigation" })).not.toBeInTheDocument();
    expect(screen.queryByText("Main Campus · Room A12")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toBeInTheDocument();
    const menu = screen.getByRole("button", { name: "Menu" });
    fireEvent.click(menu);
    expect(menu).toHaveAttribute("aria-expanded", "true");
    expect(within(screen.getByRole("navigation", { name: "Public navigation" })).getAllByRole("link")).toHaveLength(3);
    expect(screen.getByText("Main Campus · Room A12")).toBeInTheDocument();
    await expectNoA11yViolations(container);
    fireEvent.keyDown(screen.getByRole("link", { name: "Events" }), { key: "Escape" });
    expect(screen.queryByRole("navigation", { name: "Public navigation" })).not.toBeInTheDocument();
    expect(menu).toHaveFocus();
  });
  it("collapses desktop links into the menu when they no longer fit beside the name", () => {
    viewport(1280);
    vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
    vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockImplementation(function (this: HTMLElement) { return this.tagName === "UL" ? 900 : 0; });
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockImplementation(() => 400);
    header();
    expect(screen.queryByRole("navigation", { name: "Public navigation" })).not.toBeInTheDocument();
    expect(screen.getByText("Main Campus · Room A12")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Menu" }));
    expect(within(screen.getByRole("navigation", { name: "Public navigation" })).getAllByRole("link")).toHaveLength(3);
  });
});
