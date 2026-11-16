import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api/errors";
import { AttendanceReplyPage } from "./AttendanceReplyPage";
import { CrewSignupPage } from "./CrewSignupPage";

// The common pattern in this repo: lib/api is mocked WITHOUT importActual. The screens read isRetryable from
// lib/api/errors, so the gate keeps working under such a mock.
const { member } = vi.hoisted(() => ({ member: vi.fn() }));
vi.mock("../../../lib/api", () => ({ memberRequest: member }));

function show(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/member/events/:eventId/attendance" element={<AttendanceReplyPage />} />
    <Route path="/m/:slug/member/events/:eventId/attendance" element={<AttendanceReplyPage />} />
    <Route path="/member/events/:eventId/crew" element={<CrewSignupPage />} />
    <Route path="/m/:slug/member/events/:eventId/crew" element={<CrewSignupPage />} />
  </Routes></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => { member.mockReset(); });

// Decision 588: Retry only where a retry can succeed (5xx, 429, no response); a refusal gets the way out.
describe.each([
  ["attendance", "This page is not available."],
  ["crew", "This crew sign-up is not open."],
])("member event %s page", (page, refusal) => {
  it("offers Retry for an outage and asks again when pressed", async () => {
    member.mockRejectedValue(new StructuredApiError(503, { code: "service_unavailable", detail: "Down." }));
    show(`/member/events/5/${page}`);
    expect(await screen.findByText("Couldn't load this page. Try again.")).toBeVisible();
    expect(screen.queryByText(refusal)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(member).toHaveBeenCalledTimes(2));
  });

  it("treats no response at all as an outage too", async () => {
    member.mockRejectedValue(new TypeError("Failed to fetch"));
    show(`/member/events/5/${page}`);
    expect(await screen.findByRole("button", { name: "Retry" })).toBeVisible();
  });

  it.each([
    [403, "permission_denied"], [404, "not_found"], [404, "module_disabled"],
  ])("explains a %s %s refusal with a way back to the account and no Retry", async (status, code) => {
    member.mockRejectedValue(new StructuredApiError(status, { code, detail: "Refused." }));
    show(`/m/lab/member/events/5/${page}`);
    expect(await screen.findByText(refusal)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.getByRole("link", { name: "Back to your account" })).toHaveAttribute("href", "/m/lab/member");
    expect(member).toHaveBeenCalledTimes(1);
  });

  it("sends a central-portal refusal back to the central account", async () => {
    member.mockRejectedValue(new StructuredApiError(403, { code: "permission_denied", detail: "Refused." }));
    show(`/member/events/5/${page}`);
    expect(await screen.findByRole("link", { name: "Back to your account" })).toHaveAttribute("href", "/member");
  });
});
