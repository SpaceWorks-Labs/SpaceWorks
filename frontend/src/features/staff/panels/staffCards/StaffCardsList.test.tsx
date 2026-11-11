import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StaffCardsList } from "./StaffCardsList";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../../lib/api")), staffRequest }));

const card = (patch = {}) => ({ id: 31, number: "STF-0001", status: "valid", issued_at: "2026-11-01T10:00:00Z", revoked_at: null,
  revoked_reason: "", print_count: 0, check_url: "", roles_changed_since_issue: false, ...patch });
const holder = (id: number, name: string, patch = {}) => ({ membership_id: id, name, roles: [], roles_text: "Space Manager",
  machine_scope: "", eligible: true, card: null, ...patch });
const page = (results: object[]) => ({ count: results.length, next: null, previous: null, results });

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><StaffCardsList makerspaceId={4} deskPrint={false} /></QueryClientProvider>);
}

beforeEach(() => { staffRequest.mockReset(); });

describe("staff ID card register", () => {
  it("shows the roles-changed badge and reissues in one click", async () => {
    staffRequest.mockImplementation((_path: string, options?: { method?: string }) => Promise.resolve(
      options?.method === "POST" ? card()
        : page([holder(1, "Asha Menon", { card: card({ roles_changed_since_issue: true }) })])));
    mount();
    expect(await screen.findByText("Roles changed since issue")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Reissue" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/staff-cards/31/reissue", { method: "POST" }));
  });

  it("sends the search and the card filter to the server", async () => {
    staffRequest.mockResolvedValue(page([]));
    mount();
    fireEvent.change(await screen.findByRole("searchbox", { name: "Search staff" }), { target: { value: "asha" } });
    fireEvent.click(screen.getByRole("radio", { name: "No card" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(expect.stringMatching(/staff-cards\?(?=.*q=asha)(?=.*card=none)/)));
  });

  it("summarises who a bulk issue skipped and why", async () => {
    staffRequest.mockImplementation((_path: string, options?: { method?: string }) => Promise.resolve(
      options?.method === "POST" ? { issued: [card()], skipped: [{ membership_id: 2, reason: "quota" }] }
        : page([holder(1, "Asha Menon"), holder(2, "Ravi Nair")])));
    mount();
    await screen.findByText("Asha Menon");
    screen.getAllByRole("checkbox").slice(1).forEach((box) => fireEvent.click(box));
    fireEvent.click(screen.getByRole("button", { name: "Issue to 2 selected" }));
    expect(await screen.findByText("1 cards issued, 1 skipped.")).toBeVisible();
    expect(screen.getByText("Ravi Nair: over the monthly staff-card limit")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/staff-cards/bulk-issue",
      { method: "POST", body: JSON.stringify({ membership_ids: [1, 2] }) });
  });
});
