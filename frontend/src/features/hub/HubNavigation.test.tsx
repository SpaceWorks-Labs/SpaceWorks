import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { Suspense } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { HubHeader } from "./HubHeader";
import { HubFooter } from "./HubFooter";
import { LandingGate } from "./LandingGate";
import { MakerspacePage } from "../public/MakerspacePage";
import { GITHUB_URL } from "./hubLinks";

const state = vi.hoisted(() => ({ enabled: true, owner: "", accountId: 1, count: 0 }));
vi.mock("./useLandingEnabled", () => ({ useLandingEnabled: () => ({ loading: false, enabled: state.enabled }) }));
vi.mock("../hosting/hostingApi", () => ({ useHostingConfig: () => ({ data: false }) }));
vi.mock("../organizations/publicDirectoryApi", () => ({ useOrganizationDirectoryEnabled: () => false }));
vi.mock("../publicPages/pageApi", async original => ({ ...await original<typeof import("../publicPages/pageApi")>(), usePublicPage: () => ({ data: null }) }));
vi.mock("../../lib/api/sessionTokens", async original => ({ ...await original<typeof import("../../lib/api/sessionTokens")>(), getSessionOwner: () => state.owner }));
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(),
  memberRequest: vi.fn(async () => { if (!state.owner) throw new Error("signed out"); return { id: state.accountId, display_name: "Casey" }; }),
}));
vi.mock("../../lib/tenant", () => ({ useTenant: () => ({ mode: "central" }), useTenantPath: () => (part = "") => `/m/lab${part ? `/${part}` : ""}` }));
vi.mock("../inventory/usePublicInventory", () => ({
  usePublicMakerspaces: () => ({ data: Array.from({ length: state.count }, (_, i) => ({ slug: i ? `lab-${i}` : "lab", name: `Lab ${i}`, public_code: `LAB${i}`, location: "Town" })), isLoading: false, refetch: vi.fn() }),
  useTenantBootstrap: () => ({ data: { makerspace: { id: 1, slug: "lab", name: "Lab", public_site_enabled: true }, modules: [], features: [], branding: {}, theme: {} } }),
}));
function show(path = "/", gate = false) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><Suspense fallback={<p>Loading</p>}><Routes>
      <Route path="/" element={gate ? <LandingGate landing={<><HubHeader /><main><h1>Product landing</h1></main><HubFooter /></>} /> : <><HubHeader /><HubFooter /></>} />
      <Route path="/m/:slug" element={<MakerspacePage />} />
      <Route path="/about" element={<><HubHeader /><HubFooter /></>} />
    </Routes></Suspense></MemoryRouter>
  </QueryClientProvider>);
}
beforeEach(() => { state.enabled = true; state.owner = ""; state.count = 0; state.accountId = 1; });

it.each([0, 1, 3])("keeps the hub destinations reachable from / with %s spaces", async count => {
  state.count = count; show("/", true);
  await screen.findByRole("heading", { level: 1, name: count === 0 ? "Product landing" : count === 1 ? "Lab" : "Find a makerspace near you" });
  const navigation = screen.getByRole("navigation", { name: count === 1 ? "Space Works" : "Main" });
  for (const [label, href] of [["Docs", "/docs"], ["Features", "/features"], ["Spaces", "/spaces"], ["About", "/about"]]) {
    expect(within(navigation).getByRole("link", { name: label })).toHaveAttribute("href", href);
  }
  expect(within(navigation).getByRole("link", { name: /^GitHub/ })).toHaveAttribute("href", GITHUB_URL);
  const footer = screen.getByRole("contentinfo");
  for (const href of ["/docs", "/features", "/spaces", "/about", GITHUB_URL]) {
    expect(within(footer).getAllByRole("link").some(link => link.getAttribute("href") === href)).toBe(true);
  }
});
it.each(["/", "/m/lab"])("omits About when disabled on %s while keeping the other hub destinations", async path => {
  state.enabled = false; show(path);
  expect(screen.queryByRole("link", { name: "About" })).toBeNull();
  for (const href of ["/docs", "/features", "/spaces", GITHUB_URL]) {
    expect(screen.getAllByRole("link").some(link => link.getAttribute("href") === href)).toBe(true);
  }
});
it("marks About current on /about, with Home inactive", () => {
  show("/about"); const nav = screen.getByRole("navigation", { name: "Main" });
  expect(within(nav).getByRole("link", { name: "About" })).toHaveAttribute("aria-current", "page");
  expect(within(nav).getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
});
it("marks Home current on the directory homepage and returns keyboard focus when closing its phone menu", async () => {
  state.count = 3; show("/", true);
  await screen.findByRole("heading", { name: "Find a makerspace near you" });
  expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
  const menu = screen.getByRole("button", { name: "Menu" });
  fireEvent.click(menu); expect(menu).toHaveAttribute("aria-expanded", "true");
  fireEvent.keyDown(document, { key: "Escape" }); expect(menu).toHaveFocus(); expect(menu).toHaveAttribute("aria-expanded", "false");
});
it("offers the verified person's account menu instead of Sign in", async () => {
  state.owner = "1"; show();
  const account = await screen.findByRole("button", { name: "Casey" }); fireEvent.click(account);
  expect(screen.getByRole("link", { name: "My account" })).toHaveAttribute("href", "/member");
  expect(within(screen.getByRole("banner")).queryByRole("link", { name: "Sign in" })).toBeNull();
});
it("never displays an account belonging to a different session owner", async () => {
  state.owner = "2"; state.accountId = 1; show();
  expect(await within(screen.getByRole("banner")).findByRole("link", { name: "Sign in" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Casey" })).toBeNull();
});
it.each(["light", "dark"])("keeps hub navigation accessible in %s", async mode => {
  document.documentElement.classList.toggle("dark", mode === "dark");
  const { container } = show(); await expectNoA11yViolations(container);
  document.documentElement.classList.remove("dark");
});
