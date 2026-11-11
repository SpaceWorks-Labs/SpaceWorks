import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { TenantProvider } from "../../../lib/tenant";
import { TicketClaimPage } from "./TicketClaimPage";

const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"),
  memberRequest: mocks.request, getAccessToken: () => "session" }));
vi.mock("../../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Sign in to claim</p> }));

const preview = { event_id: 5, makerspace_id: 7, event_title: "Robot night", starts_at: "2026-12-01T18:00:00Z",
  ticket_type: "General", from_name: "Asha", email_matches: true };

function show(kind: "claim" | "transfer" = "claim") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab/member/ticket-claims/tok"]}><TenantProvider><Routes>
    <Route path="/m/:slug/member/ticket-claims/:token" element={<TicketClaimPage kind={kind} />} />
  </Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); });

describe("ticket claim page", () => {
  it("claims the seat for the signed-in, matching account", async () => {
    mocks.request.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method === "POST"
      ? { registration_id: 31, event_id: 5, status: "registered" } : preview));
    show();
    expect(await screen.findByText(/Robot night/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Claim my place" }));
    await waitFor(() => expect(mocks.request).toHaveBeenCalledWith("/member/ticket-claims/tok/", expect.objectContaining({ method: "POST" })));
    expect(await screen.findByText("Your place is confirmed.")).toBeVisible();
  });

  it("asks a visitor to sign in first: no account-less registration", async () => {
    mocks.request.mockRejectedValue(new StructuredApiError(401, { detail: "Sign in." }));
    show();
    expect(await screen.findByText("Sign in to claim")).toBeVisible();
  });

  it("refuses an account whose email does not match", async () => {
    mocks.request.mockResolvedValue({ ...preview, email_matches: false });
    show("transfer");
    expect(await screen.findByText(/different email address/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Accept the ticket" })).toBeDisabled();
  });
});
