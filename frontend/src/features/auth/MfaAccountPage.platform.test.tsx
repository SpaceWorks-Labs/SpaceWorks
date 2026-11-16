import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { MfaAccountPage } from "./MfaAccountPage";

vi.mock("../../lib/api", () => ({
  staffRequest: vi.fn(() => Promise.resolve({ enabled: true, required: false })),
  clearAccessToken: vi.fn(), setAccessToken: vi.fn(),
  refreshAccessToken: () => Promise.resolve(true), getAccessToken: () => null,
}));
vi.mock("../../lib/api/sessionContext", () => ({ currentSessionContext: () => "platform" }));
vi.mock("../../lib/tenant", () => ({ useOptionalTenant: () => ({ mode: "single", slug: "lab" }) }));

it("keeps the platform context in the return link on a single-tenant frontend", async () => {
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><MfaAccountPage /></MemoryRouter></QueryClientProvider>);
  // A bare /admin would resolve to the tenant's staff context on a single-tenant frontend.
  expect(await screen.findByRole("link", { name: "Return to sign-in" })).toHaveAttribute("href", "/admin?context=platform");
});
