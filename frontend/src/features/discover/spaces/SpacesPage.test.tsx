import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../../test/axe";
import type { Makerspace } from "../../../types/inventory";
import { SpacesPage } from "./SpacesPage";
import { spaceTone } from "./SpaceCard";

type QueryState = { data?: Makerspace[]; isLoading?: boolean; isError?: boolean; isFetching?: boolean; refetch: () => void };
const query = vi.hoisted(() => ({ value: {} as QueryState }));
vi.mock("../../inventory/usePublicInventory", () => ({ usePublicMakerspaces: () => query.value }));
const hosting = vi.hoisted(() => ({ value: { data: false as boolean | undefined } }));
vi.mock("../../organizations/publicDirectoryApi", () => ({ useOrganizationDirectoryEnabled: () => false }));
vi.mock("../../hosting/hostingApi", () => ({ useHostingConfig: () => hosting.value }));

const spaces: Makerspace[] = [
  { name: "Alpha Robotics Lab", public_code: "RQBG", slug: "alpha-lab", location: "Main Campus", map_url: "https://maps.example/a" },
  { name: "Beta Woodshop", public_code: "UP5U", slug: "beta-wood", location: "North Wing", logo_url: "/logo.png" },
  { name: "Gamma Fabrication Studio", public_code: "B4T8", slug: "gamma-fab", location: "Main Campus", cover_image_url: "/cover.jpg" },
];
const many = (n: number): Makerspace[] => Array.from({ length: n }, (_, i) => ({
  name: `Space ${String(i + 1).padStart(2, "0")}`, public_code: `C${i}`, slug: `space-${i + 1}`, location: i % 2 ? "East" : "West",
}));

function renderPage(state: Partial<QueryState>) {
  query.value = { refetch: vi.fn(), ...state };
  return render(<MemoryRouter initialEntries={["/spaces"]}><Routes>
    <Route path="/spaces" element={<SpacesPage />} /><Route path="/m/:slug" element={<p>Makerspace home</p>} />
  </Routes></MemoryRouter>);
}
const search = () => screen.getByRole("searchbox", { name: "Search spaces" });
const cardLinks = () => screen.getAllByRole("link").filter(link => link.getAttribute("href")?.startsWith("/m/"));

afterEach(() => {
  document.documentElement.classList.remove("dark");
  hosting.value = { data: false };
  Object.defineProperty(navigator, "onLine", { configurable: true, get: () => true });
});

describe("SpacesPage", () => {
  it("leads with one h1 in the teal hero, the space summary and the sticky search", () => {
    renderPage({ data: spaces });
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    const hero = screen.getByRole("heading", { level: 1, name: "Find a makerspace near you" }).closest("section")!;
    expect(hero).toHaveClass("sw-field-teal");
    expect(within(hero).getByText("3 makerspaces · 2 places")).toBeInTheDocument();
    expect(search().closest("form")).toHaveClass("sw-spaces-search");
    expect(screen.getByText("3 spaces")).toBeInTheDocument();
  });

  it("names each card link after its space and keeps the map link separate", () => {
    renderPage({ data: spaces });
    for (const space of spaces) expect(screen.getByRole("link", { name: space.name })).toHaveAttribute("href", `/m/${space.slug}`);
    expect(screen.getByRole("link", { name: "Open Alpha Robotics Lab in Google Maps (new tab)" })).toHaveAttribute("target", "_blank");
    expect(screen.getAllByRole("heading", { level: 3 }).map(h => h.textContent)).toEqual(spaces.map(s => s.name));
  });

  it("gives placeholder covers a stable brand field and stencils the space code", () => {
    const { container } = renderPage({ data: spaces });
    const tiles = [...container.querySelectorAll("[data-tile]")];
    expect(tiles.map(tile => tile.getAttribute("data-tile"))).toEqual([spaceTone("alpha-lab"), spaceTone("beta-wood")]);
    expect(tiles[0]).toHaveTextContent("RQBG");
  });

  it("searches, filters by place, sorts and clears", () => {
    renderPage({ data: spaces });
    fireEvent.change(search(), { target: { value: "wood" } });
    expect(screen.getByText("1 of 3 spaces")).toBeInTheDocument();
    expect(cardLinks().map(link => link.textContent)).toEqual(["Beta Woodshop"]);
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Filter by place" }), { target: { value: "Main Campus" } });
    expect(cardLinks().map(link => link.textContent)).toEqual(["Alpha Robotics Lab", "Gamma Fabrication Studio"]);
    fireEvent.change(screen.getByRole("combobox", { name: "Sort spaces" }), { target: { value: "-name" } });
    expect(cardLinks().map(link => link.textContent)).toEqual(["Gamma Fabrication Studio", "Alpha Robotics Lab"]);
  });

  it("uses the wide feature card for one or two spaces and the grid for more", () => {
    const { container, unmount } = renderPage({ data: spaces.slice(0, 2) });
    expect(container.querySelector(".sw-spaces-feature")).toHaveAttribute("data-count", "2");
    expect(container.querySelectorAll(".sw-space-card-feature")).toHaveLength(2);
    unmount();
    const grid = renderPage({ data: spaces }).container;
    expect(grid.querySelector(".sw-spaces-grid")).toBeInTheDocument();
    expect(grid.querySelector(".sw-space-card-feature")).toBeNull();
  });

  it("does not jump to the only space, and hides search when there is nothing to search", () => {
    renderPage({ data: [spaces[0]] });
    expect(screen.queryByText("Makerspace home")).toBeNull();
    expect(screen.getByRole("link", { name: "Alpha Robotics Lab" })).toBeInTheDocument();
    expect(screen.queryByRole("searchbox")).toBeNull();
  });

  it("pages 24 at a time with the shared pager", () => {
    renderPage({ data: many(30) });
    expect(cardLinks()).toHaveLength(24);
    fireEvent.click(screen.getByRole("button", { name: /Next/ }));
    expect(cardLinks().map(link => link.textContent)).toEqual(many(30).slice(24).map(s => s.name));
  });

  it("shows card-shaped skeletons and the search while loading", () => {
    renderPage({ isLoading: true });
    expect(screen.getByRole("status", { name: "Loading spaces" })).toBeInTheDocument();
    expect(search()).toBeInTheDocument();
  });

  it("explains an empty directory and points a fresh install at the platform console", () => {
    renderPage({ data: [] });
    expect(screen.getByRole("heading", { name: "No public spaces yet" })).toBeInTheDocument();
    const state = screen.getByRole("heading", { name: "No public spaces yet" }).closest(".sw-spaces-state") as HTMLElement;
    expect(within(state).getByRole("link", { name: "Platform sign-in" })).toHaveAttribute("href", "/admin");
    expect(within(state).queryByRole("link", { name: "Host your makerspace" })).toBeNull();
  });

  it("offers hosting from the empty state when hosting requests are open", () => {
    hosting.value = { data: true };
    renderPage({ data: [] });
    const state = screen.getByRole("heading", { name: "No public spaces yet" }).closest(".sw-spaces-state") as HTMLElement;
    expect(within(state).getByRole("link", { name: "Host your makerspace" })).toHaveAttribute("href", "/hosting");
  });

  it("says when a search matches nothing and clears back to everything", () => {
    renderPage({ data: spaces });
    fireEvent.change(search(), { target: { value: "zeppelin" } });
    expect(screen.getByRole("heading", { name: "No spaces match “zeppelin”" })).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Clear filters" }).at(-1)!);
    expect(cardLinks()).toHaveLength(3);
  });

  it("replaces the grid with an error and Retry, worded for offline when the browser is offline", () => {
    const refetch = vi.fn();
    const { unmount } = renderPage({ isError: true, refetch });
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load spaces");
    expect(screen.queryByRole("searchbox")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalled();
    unmount();
    Object.defineProperty(navigator, "onLine", { configurable: true, get: () => false });
    renderPage({ isError: true });
    expect(screen.getByRole("heading", { name: "You're offline" })).toBeInTheDocument();
  });

  it("keeps the cards while a background refetch fails", () => {
    renderPage({ data: spaces, isError: true });
    expect(cardLinks()).toHaveLength(3);
    expect(screen.queryByRole("alert", { name: /Couldn't load/ })).toBeNull();
  });

  it.each(["light", "dark"])("has no axe violations in %s", async (mode) => {
    document.documentElement.classList.toggle("dark", mode === "dark");
    const { container } = renderPage({ data: spaces });
    await expectNoA11yViolations(container);
  });
});

describe("SpacesPage header", () => {
  it("uses the same hub bar as the landing: Spaces current, Home/Features/Docs, GitHub, theme and sign in", () => {
    renderPage({ data: spaces });
    const bar = screen.getByRole("banner");
    expect(bar).toHaveClass("sw-hub-header");
    const main = within(bar).getByRole("navigation", { name: "Main" });
    expect(within(main).getByRole("link", { name: "Spaces" })).toHaveAttribute("aria-current", "page");
    for (const name of ["Home", "Features", "Docs"]) expect(within(main).getByRole("link", { name })).not.toHaveAttribute("aria-current");
    expect(within(bar).getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/member");
    expect(within(bar).getByRole("button", { name: "Menu" })).toBeTruthy();
    expect(screen.getAllByRole("banner")).toHaveLength(1);
  });
  it("marks the navbar logo as the splash landing spot", () => {
    const { container } = renderPage({ data: spaces });
    expect(container.querySelector("[data-sw-logo-target]")).not.toBeNull();
  });
});

vi.mock("../../hub/useLandingEnabled", () => ({ useLandingEnabled: () => ({ loading: false, enabled: true }) }));
vi.mock("../../hub/HubAccount", () => ({ HubAccount: () => <a href="/member">Sign in</a> }));
