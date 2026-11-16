import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { TenantProvider } from "../../lib/tenant";

const mocks = vi.hoisted(() => ({ request: vi.fn(), refresh: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  memberRequest: mocks.request, refreshAccessToken: mocks.refresh }));
vi.mock("../members/MemberAuthPanel", () => ({ MemberAuthPanel: ({ context }: { context?: React.ReactNode }) => <><p>Speaker account sign in</p>{context}</> }));

import { SpeakerClaimPage } from "./SpeakerClaimPage";

const claimed = { speaker_id: 4, display_name: "Ada Lovelace", event: { id: 2, title: "Lightning talks", starts_at: "2026-11-01T10:00:00Z", ends_at: "2026-11-01T12:00:00Z" } };
let claimResult: () => Promise<unknown>;

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab/member/speaker-claim"]}><TenantProvider><Routes>
    <Route path="/m/:slug/member/speaker-claim" element={<SpeakerClaimPage />} />
  </Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  window.sessionStorage.clear();
  window.history.replaceState(null, "", "/m/lab/member/speaker-claim#token=speaker-secret");
  mocks.request.mockReset(); mocks.refresh.mockReset(); mocks.refresh.mockResolvedValue(true);
  claimResult = () => Promise.resolve(claimed);
  mocks.request.mockImplementation((path: string) => path === "/auth/me" ? Promise.resolve({ username: "ada" }) : claimResult());
});

describe("speaker claim", () => {
  it("reads the token from the fragment, clears it, and claims only on request", async () => {
    show();
    await screen.findByText("Signed in as ada.");
    expect(window.location.hash).toBe("");
    expect(window.location.search).toBe("");
    expect(mocks.request).not.toHaveBeenCalledWith("/member/event-speaker-claims/", expect.anything());
    fireEvent.click(screen.getByRole("button", { name: "Claim speaker invitation" }));
    expect(await screen.findByRole("heading", { name: "You're listed as a speaker" })).toBeVisible();
    expect(screen.getByText(/linked to Lightning talks/)).toBeVisible();
    expect(mocks.request).toHaveBeenCalledWith("/member/event-speaker-claims/", { method: "POST", body: JSON.stringify({ token: "speaker-secret" }) });
    expect(window.sessionStorage.getItem("spaceworks.speakerClaim")).toBeNull();
  });

  it("sends a signed-out visitor through sign-in and keeps the token for this tab only", async () => {
    mocks.refresh.mockResolvedValue(false);
    show();
    expect(await screen.findByText("Speaker account sign in")).toBeVisible();
    expect(window.location.hash).toBe("");
    expect(window.sessionStorage.getItem("spaceworks.speakerClaim")).toBe("speaker-secret");
    expect(mocks.request).not.toHaveBeenCalledWith("/member/event-speaker-claims/", expect.anything());
  });

  it("explains an expired or used link", async () => {
    claimResult = () => Promise.reject(new StructuredApiError(404, { detail: "Not found." }));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Claim speaker invitation" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/no longer valid/));
    expect(window.sessionStorage.getItem("spaceworks.speakerClaim")).toBeNull();
  });

  it("refuses to claim without a token", async () => {
    window.history.replaceState(null, "", "/m/lab/member/speaker-claim");
    show();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/missing its token/));
    expect(screen.getByRole("button", { name: "Claim speaker invitation" })).toBeDisabled();
  });
});
