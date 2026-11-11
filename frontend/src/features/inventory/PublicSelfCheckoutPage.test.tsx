/** Inventory journey (0.12.0): who may borrow or return at the standalone self-checkout page. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({ token: "", refresh: vi.fn(), features: [] as string[], access: undefined as "contact" | undefined }));
vi.mock("../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../lib/api")>(),
  getAccessToken: () => state.token, refreshAccessToken: state.refresh, tenantPublicRequest: vi.fn() }));
vi.mock("../../lib/tenant", async importOriginal => ({ ...await importOriginal<typeof import("../../lib/tenant")>(),
  useTenant: () => ({ mode: "single", slug: "lab", bootstrap: { makerspace: { id: 7, name: "Lab", request_access: state.access }, branding: {}, modules: [], features: state.features } }),
  useTenantPath: () => (part = "") => `/${part}`,
}));
vi.mock("./usePublicInventory", () => ({ useTenantBootstrap: () => ({ data: undefined, isLoading: false, isError: false }) }));
vi.mock("./PublicEvidenceUpload", () => ({ PublicEvidenceUpload: ({ evidenceType }: { evidenceType: string }) => <p>{evidenceType} photo</p> }));
vi.mock("../../components/SiteFooter", () => ({ SiteFooter: () => null }));

import { PublicSelfCheckoutPage } from "./PublicSelfCheckoutPage";

function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><PublicSelfCheckoutPage /></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => {
  state.token = ""; state.access = undefined; state.features = ["inventory.self_checkout"];
  state.refresh.mockReset(); state.refresh.mockResolvedValue(false);
});

it("asks a signed-out visitor to sign in before any photo, where member accounts are on", async () => {
  show();
  expect(await screen.findByText("Sign in to your account at Lab to borrow or return a tool here.")).toBeVisible();
  expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/member");
  expect(screen.queryByText("issue photo")).toBeNull();
});

it("opens the borrow step for a restored session", async () => {
  state.refresh.mockResolvedValue(true);
  show();
  expect(await screen.findByText("issue photo")).toBeVisible();
  expect(screen.getByRole("radio", { name: "Borrow" })).toBeVisible();
});

it("offers returns only on the contact path while account-less checkout is off", async () => {
  state.access = "contact";
  show();
  expect(await screen.findByText(/Borrowing without an account is switched off here/)).toBeVisible();
  expect(screen.queryByRole("radio", { name: "Borrow" })).toBeNull();
  expect(screen.getByText("return photo")).toBeVisible();
  expect(screen.getByLabelText("Return condition notes")).toBeVisible();
  expect(state.refresh).not.toHaveBeenCalled();
});

it("lets an account-less visitor borrow once the switch is on", async () => {
  state.access = "contact"; state.features = ["inventory.self_checkout", "inventory.contact_self_checkout"];
  show();
  expect(await screen.findByRole("radio", { name: "Borrow" })).toBeVisible();
  expect(screen.getByText("issue photo")).toBeVisible();
});
