import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ staffRequest: vi.fn(), refreshAccessToken: vi.fn(), fetchMe: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), ...api }));

import { apiError } from "../../lib/api/errors";
import { OrganizationInvitationRedeemPage } from "./OrganizationInvitationRedeemPage";

const mount = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
  <MemoryRouter initialEntries={["/organization-invitations/redeem/tok"]}>
    <Routes><Route path="/organization-invitations/redeem/:token" element={<OrganizationInvitationRedeemPage />} /></Routes>
  </MemoryRouter>
</QueryClientProvider>);

beforeEach(() => {
  api.staffRequest.mockReset();
  api.refreshAccessToken.mockResolvedValue(true);
  api.fetchMe.mockResolvedValue({ id: 1, username: "member" });
});

// A used, expired or revoked invitation is refused again on every retry, so the page offers the way out instead.
it.each([400, 403, 404, 409])("gives a %s refusal the way out, not Retry", async (status) => {
  api.staffRequest.mockRejectedValue(apiError(status, { detail: "This invitation can no longer be used." }));
  mount();
  expect(await screen.findByRole("link", { name: "Return to directory" })).toHaveAttribute("href", "/");
  expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  expect(api.staffRequest).toHaveBeenCalledTimes(1);
});

it("offers Retry for a server-side failure and redeems on the second attempt", async () => {
  api.staffRequest.mockRejectedValueOnce(apiError(503, { detail: "Service unavailable." }));
  api.staffRequest.mockResolvedValueOnce({});
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Retry" }));
  await waitFor(() => expect(screen.getByRole("heading", { name: "You're in" })).toBeInTheDocument());
  expect(api.staffRequest).toHaveBeenCalledTimes(2);
});
