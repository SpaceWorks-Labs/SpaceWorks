import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { VerifyStaffPanel } from "./VerifyStaffPanel";

const { staffRequest, getAccessToken, refreshAccessToken } = vi.hoisted(() => ({
  staffRequest: vi.fn(), getAccessToken: vi.fn(), refreshAccessToken: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...(await vi.importActual<object>("../../lib/api")), staffRequest, getAccessToken, refreshAccessToken }));

const panel = { makerspace_id: 4, membership_id: 9, member_url: "/admin/members?id=9", card_state: "valid",
  member: { name: "Priya Raman", number: "TNK-0042", plan: "Monthly", valid_until: "31 Dec 2026" },
  actions: [{ key: "renew", method: "POST", path: "memberships/9/extend" },
    { key: "revoke_card", method: "POST", path: "member-cards/12/revoke" }] };

const mount = () => render(<QueryClientProvider client={new QueryClient()}><VerifyStaffPanel token="tok" onChanged={vi.fn()} /></QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); getAccessToken.mockReset().mockReturnValue("jwt"); refreshAccessToken.mockReset().mockResolvedValue(false); });

describe("staff panel on the card check page", () => {
  it("renders nothing for a visitor with no session, and never calls the staff route", async () => {
    getAccessToken.mockReturnValue(null);
    const view = mount();
    await waitFor(() => expect(refreshAccessToken).toHaveBeenCalled());
    expect(staffRequest).not.toHaveBeenCalled();
    expect(view.container).toBeEmptyDOMElement();
  });

  it("renders nothing when the server answers 404", async () => {
    staffRequest.mockRejectedValue(new Error("not found"));
    const view = mount();
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    expect(view.container).toBeEmptyDOMElement();
  });

  it("shows the member and revokes with a note through the existing route", async () => {
    staffRequest.mockImplementation((_path: string, options?: { method?: string }) => Promise.resolve(options?.method === "POST" ? {} : panel));
    mount();
    expect(await screen.findByText("Priya Raman")).toBeVisible();
    expect(screen.getByRole("link", { name: "Open member to renew or record a payment" })).toHaveAttribute("href", "/admin/members?id=9");
    fireEvent.click(screen.getByRole("button", { name: "Revoke card" }));
    const confirm = screen.getAllByRole("button", { name: "Revoke card" }).at(-1)!;
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Lost at the market" } });
    fireEvent.click(confirm);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/member-cards/12/revoke",
      { method: "POST", body: JSON.stringify({ note: "Lost at the market" }) }, "person"));
  });
});
