import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BookingStaffInvitePage } from "./BookingStaffInvitePage";

const { request, logout, me, refresh } = vi.hoisted(() => ({ request: vi.fn(), logout: vi.fn(), me: vi.fn(), refresh: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  staffRequest: request, logout, fetchMe: me, refreshAccessToken: refresh }));
// The sign-in page carries the invitation's context and its Cancel action in its own slots.
vi.mock("../members/MemberAuthPanel", () => ({ MemberAuthPanel: ({ context, footer }: { context?: React.ReactNode; footer?: React.ReactNode }) => <><p>Invited account sign-in</p>{context}{footer}</> }));
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/staff/booking-invite"]}><Routes>
    <Route path="/staff/booking-invite" element={<BookingStaffInvitePage />} />
    <Route path="/admin/assigned-events" element={<p>Member helper workspace</p>} />
    <Route path="/" element={<p>Invitation cancelled</p>} />
  </Routes></MemoryRouter></QueryClientProvider>);
}
describe("booking resource staff invitation redemption", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    window.history.replaceState(null, "", "/staff/booking-invite#token=invite-secret");
    request.mockReset(); logout.mockReset(); logout.mockResolvedValue(undefined);
    me.mockResolvedValue({ username: "invitee", makerspaces: [] }); refresh.mockResolvedValue(true);
    request.mockResolvedValue({ id: 8, permissions: ["check_in"] });
  });
  it("captures the fragment, redeems, and opens the helper workspace without signing out", async () => {
    setup();
    await screen.findByText("Signed in as invitee.");
    expect(window.location.hash).toBe("");
    expect(request).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Accept staff invitation" }));
    await screen.findByText(/Your resource staff access is active/);
    expect(window.sessionStorage.getItem("spaceworks.bookingStaffInvite")).toBeNull();
    expect(request).toHaveBeenCalledWith("/admin/booking-staff-invites/redeem/", {
      method: "POST", body: JSON.stringify({ token: "invite-secret" }),
    });
    expect(logout).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Open helper workspace" }));
    await screen.findByText("Member helper workspace"); expect(logout).not.toHaveBeenCalled();
  });
  it("shows unavailable, email and authority failures without elevating the session", async () => {
    request.mockRejectedValue(new Error("A matching verified email is required.")); setup();
    fireEvent.click(await screen.findByRole("button", { name: "Accept staff invitation" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("matching verified email"));
    expect(logout).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Open helper workspace" })).not.toBeInTheDocument();
  });
  it("uses the account sign-in flow before redemption", async () => {
    refresh.mockResolvedValue(false); setup();
    await screen.findByText("Invited account sign-in"); expect(request).not.toHaveBeenCalled();
  });
  it.each([true, false])("clears the pending token on cancellation with session=%s", async (signedIn) => {
    refresh.mockResolvedValue(signedIn); setup();
    await screen.findByText(signedIn ? "Signed in as invitee." : "Invited account sign-in");
    fireEvent.click(await screen.findByRole("button", { name: "Cancel invitation" }));
    await screen.findByText("Invitation cancelled");
    expect(window.sessionStorage.getItem("spaceworks.bookingStaffInvite")).toBeNull();
    expect(request).not.toHaveBeenCalled();
  });
  it("restores the fragment-stripped token after a normal reload and redeems it", async () => {
    window.history.replaceState(null, "", "/staff/booking-invite");
    window.sessionStorage.setItem("spaceworks.bookingStaffInvite", "pending-invitation");
    setup();
    fireEvent.click(await screen.findByRole("button", { name: "Accept staff invitation" }));
    await screen.findByText(/Your resource staff access is active/);
    expect(request).toHaveBeenCalledWith("/admin/booking-staff-invites/redeem/", {
      method: "POST", body: JSON.stringify({ token: "pending-invitation" }),
    });
    expect(window.sessionStorage.getItem("spaceworks.bookingStaffInvite")).toBeNull();
  });
});
