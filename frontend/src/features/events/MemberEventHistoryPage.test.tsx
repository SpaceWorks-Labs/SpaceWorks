import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { TenantProvider } from "../../lib/tenant";

const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  memberRequest: mocks.request, getAccessToken: () => "session" }));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: () => ({ data: { makerspace: { id: 7, name: "Lab" } } }) }));
vi.mock("../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>History account sign in</p> }));

import { MemberEventHistoryPage } from "./MemberEventHistoryPage";

const event = (id: number, title: string) => ({ id, title, starts_at: "2026-09-01T10:00:00Z", ends_at: "2026-09-01T12:00:00Z", location: "Lab", status: "completed" });
let historyResult: () => Promise<unknown>;

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab/member/events/history"]}><TenantProvider><Routes>
    <Route path="/m/:slug/member/events/history" element={<MemberEventHistoryPage />} />
  </Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  mocks.request.mockReset();
  historyResult = () => Promise.resolve({ counts: { registered: 1, attended: 1, cancelled: 0, speaking: 1 },
    registrations: [{ registration_id: 3, status: "attended", event: event(1, "Open night") }],
    speaking: [{ speaker_id: 9, role: "speaker", occurred_at: "2026-08-01T10:00:00Z", event: event(2, "Lightning talks") }] });
  mocks.request.mockImplementation((path: string) => path === "/auth/me" ? Promise.resolve({ id: 19 }) : historyResult());
});

describe("member event history", () => {
  it("shows registrations and talks for an account with no membership", async () => {
    show();
    expect(await screen.findByText("Lightning talks")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Spoke at" })).toBeVisible();
    expect(screen.getByText("Open night")).toBeVisible();
    expect(mocks.request).toHaveBeenCalledWith("/member/makerspaces/7/event-history/");
  });

  it("answers a 403 with a friendly empty state, not an error", async () => {
    historyResult = () => Promise.reject(new StructuredApiError(403, { detail: "You do not have permission." }));
    show();
    expect(await screen.findByText(/No event history here yet/)).toBeVisible();
    expect(screen.queryByText("You do not have permission.")).toBeNull();
  });

  it("asks a signed-out visitor to sign in", async () => {
    mocks.request.mockImplementation(() => Promise.reject(new StructuredApiError(401, { detail: "Sign in." })));
    show();
    await waitFor(() => expect(screen.getByText("History account sign in")).toBeVisible());
  });
});
