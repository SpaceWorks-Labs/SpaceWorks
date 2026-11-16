import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest, StructuredApiError } from "../../lib/api";
import { StaffCheckInDialog } from "./StaffCheckInDialog";

vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), staffRequest: vi.fn() }));

const holder = { id: 55, display_name: "Grace Guest", pass_valid_until: "2026-11-12T18:00:00Z", waiver_on_file: false };

function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <StaffCheckInDialog makerspaceId={3} presets={[60, 120]} onClose={() => undefined} onDone={() => undefined} />
  </QueryClientProvider>);
}

describe("StaffCheckInDialog with guest passes", () => {
  beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

  it("finds a guest-pass holder and stamps the waiver while checking them in", async () => {
    vi.mocked(staffRequest).mockImplementation(async (path: string) => {
      if (path.startsWith("/admin/memberships")) return { results: [] };
      if (path.includes("/check-in-guests?")) return { results: [holder] };
      return {};
    });
    show();
    fireEvent.change(screen.getByLabelText(/Find a member or guest/), { target: { value: "grace" } });
    fireEvent.click(await screen.findByRole("radio", { name: /Grace Guest/ }));
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/presence-sessions/check-in-guests?q=grace");
    expect(screen.getByText(/Guest pass until .* · no waiver yet/)).toBeVisible();
    fireEvent.click(screen.getByLabelText("Waiver accepted at the desk"));
    fireEvent.click(screen.getByRole("button", { name: /^Check in$/ }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/presence-sessions/check-in",
      { method: "POST", body: JSON.stringify({ account_id: 55, duration_minutes: 120, waiver_accepted_at_desk: true }) }));
  });

  it("shows a waiver already on file and asks for no desk stamp", async () => {
    vi.mocked(staffRequest).mockImplementation(async (path: string) => {
      if (path.startsWith("/admin/memberships")) return { results: [] };
      if (path.includes("/check-in-guests?")) return { results: [{ ...holder, waiver_on_file: true }] };
      return {};
    });
    show();
    fireEvent.change(screen.getByLabelText(/Find a member or guest/), { target: { value: "grace" } });
    fireEvent.click(await screen.findByRole("radio", { name: /Grace Guest/ }));
    expect(screen.getByText(/waiver on file/)).toBeVisible();
    expect(screen.queryByLabelText("Waiver accepted at the desk")).toBeNull();
  });

  it("keeps working as a member search when the guest search is refused, and explains a missing waiver", async () => {
    vi.mocked(staffRequest).mockImplementation(async (path: string) => {
      if (path.startsWith("/admin/memberships")) return { results: [{ id: 1, user: { id: 9, username: "ada", display_name: "Ada" } }] };
      if (path.includes("check-in-guests")) throw new StructuredApiError(404, { code: "feature_disabled" });
      throw new StructuredApiError(403, { code: "waiver_acceptance_required", detail: "raw" });
    });
    show();
    fireEvent.change(screen.getByLabelText(/Find a member or guest/), { target: { value: "ada" } });
    fireEvent.click(await screen.findByRole("radio", { name: /Ada/ }));
    expect(screen.queryByLabelText("Waiver accepted at the desk")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /^Check in$/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("hasn't accepted the waiver");
  });
});
