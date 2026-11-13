import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { AppRoutes } from "../../AppRoutes";

const state = vi.hoisted(() => ({ enabled: true, mode: "central" }));
vi.mock("./useLandingEnabled", () => ({ useLandingEnabled: () => ({ loading: false, enabled: state.enabled }) }));
vi.mock("../NotFoundPage", () => ({ NotFoundPage: () => <h1>Not found</h1> }));
vi.mock("./HubLandingPage", () => ({ HubLandingPage: () => <h1>Full product landing</h1> }));
vi.mock("../discover/spaces/SpacesPage", () => ({ SpacesPage: () => <h1>Spaces directory</h1> }));
vi.mock("../public/FamilyHome", () => ({ RouteFallback: () => <p>Opening</p>, FamilyHome: () => <h1>Space home</h1> }));
vi.mock("../../lib/tenant", () => ({ useTenant: () => ({ mode: state.mode, slug: "lab", modules: new Set() }) }));
beforeEach(() => { state.enabled = true; state.mode = "central"; });
it.each(["central", "single"] as const)("mounts the full landing at /about in %s mode", async mode => {
  state.mode = mode;
  render(<MemoryRouter initialEntries={["/about"]}><AppRoutes mode={mode} landing={<h1>Homepage</h1>} /></MemoryRouter>);
  expect(await screen.findByRole("heading", { name: "Full product landing" })).toBeVisible();
});
it.each(["central", "single"] as const)("redirects /about to / with landing disabled in %s mode", async mode => {
  state.mode = mode; state.enabled = false;
  render(<MemoryRouter initialEntries={["/about"]}><AppRoutes mode={mode} landing={<h1>Homepage</h1>} /></MemoryRouter>);
  expect(await screen.findByRole("heading", { name: mode === "central" ? "Homepage" : "Space home" })).toBeVisible();
});
it.each(["central", "single"] as const)("keeps /spaces reachable from the hub links in %s mode", async mode => {
  state.mode = mode;
  render(<MemoryRouter initialEntries={["/spaces"]}><AppRoutes mode={mode} landing={<h1>Homepage</h1>} /></MemoryRouter>);
  expect(await screen.findByRole("heading", { name: "Spaces directory" })).toBeVisible();
});

it.each([["lab", "Space home"], ["another-space", "Not found"]])("guards the single-tenant directory card alias for %s", async (slug, heading) => {
  state.mode = "single";
  render(<MemoryRouter initialEntries={[`/m/${slug}`]}><AppRoutes mode="single" landing={<h1>Homepage</h1>} /></MemoryRouter>);
  expect(await screen.findByRole("heading", { name: heading })).toBeVisible();
});
