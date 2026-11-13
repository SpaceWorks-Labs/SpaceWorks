import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../test/axe";
import type { Makerspace } from "../types/inventory";
import { LandingPage } from "./LandingPage";
import { spaceTileTone } from "./landing/SpaceCard";

const query = vi.hoisted(() => ({ value: {} as { data?: Makerspace[]; isLoading?: boolean; isError?: boolean; refetch: () => void } }));
vi.mock("./inventory/usePublicInventory", () => ({ usePublicMakerspaces: () => query.value }));
const hosting = vi.hoisted(() => ({ value: { data: false as boolean | undefined, isPending: false } }));
vi.mock("./hosting/hostingApi", () => ({ useHostingConfig: () => hosting.value }));

const spaces: Makerspace[] = [
  { name: "Alpha Robotics Lab", public_code: "RQBG", slug: "alpha-lab", location: "Main Campus" },
  { name: "Beta Woodshop", public_code: "UP5U", slug: "beta-wood", location: "North Wing" },
  { name: "Gamma Fabrication Studio", public_code: "B4T8", slug: "gamma-fab", location: "Downtown", cover_image_url: "/cover.jpg" },
];

function renderLanding(state: Partial<typeof query.value>) {
  query.value = { refetch: vi.fn(), ...state };
  return render(<MemoryRouter initialEntries={["/"]}><Routes>
    <Route path="/" element={<LandingPage />} /><Route path="/m/:slug" element={<p>Makerspace home</p>} />
  </Routes></MemoryRouter>);
}

afterEach(() => { document.documentElement.classList.remove("dark"); hosting.value = { data: false, isPending: false }; });

describe("LandingPage", () => {
  it("opens with the teal hero: one h1, one accent phrase, the Citron search and the facets", () => {
    const { container } = renderLanding({ data: spaces });
    const title = screen.getByRole("heading", { level: 1, name: "Less searching. More making." });
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(title).toHaveClass("sw-hero-title");
    expect(container.querySelectorAll(".sw-hero-title, .font-accent")).toHaveLength(1);
    const hero = title.closest("section")!;
    expect(hero).toHaveClass("sw-field-teal");
    expect(within(hero).getByRole("searchbox", { name: "Search makerspaces" })).toHaveClass("bg-success");
    expect(hero.querySelector("[data-facets]")).toHaveAttribute("aria-hidden", "true");
  });

  it("filters spaces, announces the count and clears the search", () => {
    renderLanding({ data: spaces });
    expect(screen.getByText("3 / 3 spaces")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search makerspaces" }), { target: { value: "wood" } });
    expect(screen.getByText("1 / 3 spaces")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open makerspace Beta Woodshop" })).toHaveAttribute("href", "/m/beta-wood");
    expect(screen.queryByRole("link", { name: "Open makerspace Alpha Robotics Lab" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(screen.getByText("3 / 3 spaces")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Clear search" })).not.toBeInTheDocument();
  });

  it("keeps every link, configured banner and makerspace overview card", () => {
    renderLanding({ data: spaces });
    expect(screen.getAllByRole("link", { name: "About" }).some(link => link.getAttribute("href") === "/about")).toBe(true);
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/member");
    expect(screen.getByRole("link", { name: /License/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Platform sign-in" })).toHaveAttribute("href", "/admin");
    for (const space of spaces) expect(screen.getByRole("link", { name: `Open makerspace ${space.name}` })).toHaveAttribute("href", `/m/${space.slug}`);
    expect(screen.getByRole("img", { name: "Gamma Fabrication Studio banner" })).toBeInTheDocument();
  });

  it("gives each placeholder cover a stable solid brand tile", () => {
    const { container } = renderLanding({ data: spaces });
    const tiles = [...container.querySelectorAll("[data-tile]")];
    expect(tiles.map(tile => tile.getAttribute("data-tile"))).toEqual([spaceTileTone("alpha-lab"), spaceTileTone("beta-wood")]);
  });

  it("shows the hero while spaces load, and Retry on error", () => {
    const { unmount } = renderLanding({ isLoading: true });
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Loading spaces" })).toBeInTheDocument();
    unmount();
    const refetch = vi.fn();
    renderLanding({ isError: true, refetch });
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("tells an empty directory what to expect", () => {
    renderLanding({ data: [] });
    expect(screen.getByText("No public spaces yet. They appear here once a space publishes its public site.")).toBeInTheDocument();
  });

  it("goes straight to the only space", () => {
    renderLanding({ data: [spaces[0]] });
    expect(screen.getByText("Makerspace home")).toBeInTheDocument();
  });

  it("offers hosting and keeps the directory for a single space when hosting requests are open", () => {
    hosting.value = { data: true, isPending: false };
    renderLanding({ data: [spaces[0]] });
    expect(screen.queryByText("Makerspace home")).toBeNull();
    const links = screen.getAllByRole("link", { name: "Host your makerspace" });
    expect(links.length).toBeGreaterThanOrEqual(2);
    for (const link of links) expect(link).toHaveAttribute("href", "/hosting");
    expect(screen.getByRole("navigation", { name: "Footer" })).toContainElement(links.at(-1)!);
  });

  it("has no hosting link without the flag, and waits for the config before skipping to the only space", () => {
    renderLanding({ data: spaces });
    expect(screen.queryByRole("link", { name: "Host your makerspace" })).toBeNull();
    hosting.value = { data: undefined, isPending: true };
    renderLanding({ data: [spaces[0]] });
    expect(screen.queryByText("Makerspace home")).toBeNull();
  });

  it.each(["light", "dark"])("has no axe violations in %s", async (mode) => {
    document.documentElement.classList.toggle("dark", mode === "dark");
    const { container } = renderLanding({ data: spaces });
    await expectNoA11yViolations(container);
  });
});
