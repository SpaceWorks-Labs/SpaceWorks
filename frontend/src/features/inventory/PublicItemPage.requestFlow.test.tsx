import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { TenantBootstrap } from "../../lib/api";
import { PublicItemPage } from "./PublicItemPage";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { useMemberReturn } from "../members/useMemberReturn";
import { submitPublicRequest } from "./api";

const state = vi.hoisted(() => ({ owner: "", desktop: false, modules: ["public_inventory", "request_workflow", "member_accounts"], returned: "", bootstrapError: false, retry: vi.fn() }));
const openSignIn = vi.fn();
const product = { id: 4, name: "Drill", description: "Public drill", availability: { mode: "exact_count", count: 8, label: "Available" } };
const bootstrap = (): TenantBootstrap => ({
  makerspace: { id: 1, slug: "forge", name: "Forge", public_code: "FRGE", location: "Town", geofence_enabled: false, membership_policy: "open", public_site_enabled: true, public_inventory_enabled: true },
  modules: state.modules, features: ["loans.enabled"], workflows: [], edition: "makerspace", frontend: { type: "makerspace", hostname: "", allowed_origins: [] },
  branding: {}, theme: {}, email_enabled: false, public_api: { base_url: "/api/v1", publishable_key: "", inventory_path: "" },
});
vi.mock("./usePublicInventory", () => ({ useTenantBootstrap: () => state.bootstrapError ? { error: new Error("offline"), refetch: state.retry } : { data: bootstrap() } }));
vi.mock("./useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: state.owner }) }));
vi.mock("../../lib/api/sessionTokens", async original => ({ ...await original<typeof import("../../lib/api/sessionTokens")>(), hasSessionIdentity: () => Boolean(state.owner), getSessionOwner: () => state.owner }));
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(),
  tenantPublicRequest: vi.fn(async () => product), memberRequest: vi.fn(async () => ({ id: 1 })),
  publicV1Request: vi.fn(async () => ({ access: "signed-in" })), setAccessToken: () => { state.owner = "1"; },
}));
vi.mock("../../lib/tenant", async original => ({ ...await original<typeof import("../../lib/tenant")>(),
  useTenant: () => ({ mode: "central" }), useTenantPath: () => (part = "") => `/m/forge${part ? `/${part}` : ""}`,
}));
vi.mock("../../components/layouts/useLayoutMedia", () => ({ useLayoutMedia: (query: string) => query.includes("min-width") ? state.desktop : !state.desktop }));
vi.mock("./api", () => ({ submitPublicRequest: vi.fn(async () => ({ id: 24 })) }));
vi.mock("../payments/PricePreview", () => ({ PricePreview: () => null }));
vi.mock("./WaitlistJoin", () => ({ WaitlistJoin: () => null }));
vi.mock("../auth/SocialSignInButtons", () => ({ SocialSignInButtons: () => null }));
vi.mock("../auth/usePublicSignInConfig", () => ({ usePublicSignInConfig: () => ({ selfServeAccounts: true, passwordLogin: true, passkeysEnabled: false }) }));

function SignIn() {
  const returning = useMemberReturn(new URLSearchParams(window.location.search), { unauthenticated: true, signedIn: false, openSignIn });
  return <MemberAuthPanel makerspaceSlug="forge" onAuthenticated={() => { state.returned = returning.afterSignIn() ?? ""; }} />;
}
function show(path: string) {
  window.history.replaceState(null, "", path);
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/m/:slug/items/:itemId" element={<PublicItemPage />} /><Route path="/m/:slug/member" element={<SignIn />} />
  </Routes></MemoryRouter></QueryClientProvider>);
}
async function openRequest() {
  await screen.findByRole("heading", { level: 1, name: "Drill" });
  if (!state.desktop && !screen.queryByRole("dialog")) fireEvent.click(screen.getByRole("button", { name: "Request" }));
  return screen.findByRole("spinbutton", { name: "Quantity" });
}
beforeEach(() => {
  state.owner = ""; state.desktop = false; state.returned = ""; state.bootstrapError = false;
  state.modules = ["public_inventory", "request_workflow", "member_accounts"]; state.retry.mockClear();
  vi.mocked(submitPublicRequest).mockClear(); window.sessionStorage.clear();
});
afterEach(() => { window.history.replaceState(null, "", "/"); window.sessionStorage.clear(); });
it.each([false, true])("returns through real sign-in to the same item and quantity, submits, and links My requests (desktop=%s)", async desktop => {
  state.desktop = desktop;
  const path = "/m/forge/items/4-drill?source=home";
  let view = show(path);
  fireEvent.change(await openRequest(), { target: { value: "3" } });
  const signIn = screen.getByRole("link", { name: "Sign in to borrow" });
  const href = signIn.getAttribute("href")!;
  expect(href).toBe(`/m/forge/member?next=${encodeURIComponent(path)}`);
  fireEvent.click(signIn); view.unmount();
  view = show(href);
  expect(screen.getByRole("radio", { name: "Create account" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "casey@example.test" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(state.returned).toBe(path)); view.unmount();
  show(state.returned);
  // No extra Request click after return: the phone sheet must restore itself.
  expect(await screen.findByRole("spinbutton", { name: "Quantity" })).toHaveValue(3);
  fireEvent.change(screen.getByLabelText("Request purpose"), { target: { value: "Build a community desk" } });
  const submit = screen.getByRole("button", { name: "Submit request" });
  await waitFor(() => expect(submit).toBeEnabled()); fireEvent.click(submit);
  expect(await screen.findByRole("heading", { name: "Request submitted" })).toBeVisible();
  expect(submitPublicRequest).toHaveBeenCalledWith("forge", expect.objectContaining({ items: [{ product_id: 4, quantity: 3 }], requested_for: "Build a community desk" }));
  expect(screen.getByRole("link", { name: "My requests" })).toHaveAttribute("href", "/m/forge/member/loans/history");
});
it("keeps quantity and purpose when the phone sheet closes", async () => {
  show("/m/forge/items/4"); fireEvent.change(await openRequest(), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Request purpose"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  fireEvent.click(screen.getByRole("button", { name: "Request" }));
  expect(screen.getByRole("spinbutton", { name: "Quantity" })).toHaveValue(2);
  expect(screen.getByLabelText("Request purpose")).toHaveValue("Workshop");
});
it.each(["public_inventory", "request_workflow"])("offers no Request action when %s is off", async module => {
  state.modules = state.modules.filter(value => value !== module); show("/m/forge/items/4");
  await screen.findByRole("heading", { level: 1, name: "Drill" });
  expect(screen.queryByRole("button", { name: "Request" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Item details" }));
  expect(screen.queryByRole("link", { name: "Sign in to borrow" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Submit request" })).toBeNull();
});
it("shows bootstrap errors with retry instead of loading forever", async () => {
  state.bootstrapError = true; show("/m/forge/items/4");
  expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load this space");
  fireEvent.click(screen.getByRole("button", { name: /Retry|Try again/ })); expect(state.retry).toHaveBeenCalled();
});

it("limits quantities to the cart handoff maximum so sign-in cannot reduce a chosen quantity", async () => {
  const original = product.availability.count; product.availability.count = 200;
  try {
    show("/m/forge/items/4"); const quantity = await openRequest();
    expect(quantity).toHaveAttribute("max", "99");
    fireEvent.change(quantity, { target: { value: "120" } }); expect(quantity).toHaveValue(1);
  } finally { product.availability.count = original; }
});
