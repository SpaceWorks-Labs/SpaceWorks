import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { BookingStaffAccess } from "./BookingStaffAccess";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest: request }));
const grant = { id: 7, user: 42, permissions: ["check_in"], revoked_at: null };
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><BookingStaffAccess target={{ id: 5 }} /></QueryClientProvider>);
  return client;
}
describe("booking staff access management", () => {
  beforeEach(() => {
    request.mockReset();
    request.mockImplementation(async (path: string, init?: RequestInit) => {
      if (init?.method === "POST" && path.endsWith("staff-invites/")) return { id: 9, token: "secret-invitation-token" };
      if (init?.method) return grant;
      return page(path.includes("staff-grants") ? [grant] : []);
    });
  });
  it("invites with selected permissions and displays the link once", async () => {
    const client = setup();
    await screen.findByText("Account #42");
    fireEvent.change(screen.getByLabelText("Invite email"), { target: { value: "staff@example.test" } });
    expect(screen.getByRole("button", { name: "Invite staff" })).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Check in"));
    fireEvent.click(screen.getByRole("button", { name: "Invite staff" }));
    await screen.findByDisplayValue(/staff\/booking-invite#token=secret-invitation-token/);
    expect(request).toHaveBeenCalledWith("/admin/spaces/5/staff-invites/", expect.objectContaining({ method: "POST",
      body: JSON.stringify({ email: "staff@example.test", send_email: true, permissions: ["check_in"] }) }));
    expect(JSON.stringify(client.getQueryCache().getAll().map((query) => query.state.data))).not.toContain("secret-invitation-token");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss link" }));
    expect(screen.queryByDisplayValue(/secret-invitation-token/)).not.toBeInTheDocument();
  });
  it("edits, invalidates and revokes grants", async () => {
    setup(); await screen.findByText("Account #42");
    fireEvent.click(screen.getByRole("button", { name: "Edit account #42" }));
    const fields = screen.getByRole("group", { name: "Permissions for account #42" });
    fireEvent.click(fields.querySelectorAll("input")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Save permissions" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/booking-staff-grants/7/", expect.objectContaining({ method: "PATCH" })));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Save permissions" })).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Revoke account #42" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/booking-staff-grants/7/revoke/", expect.objectContaining({ method: "POST" })));
  });
  it("has accessible permission fields and management controls", async () => {
    setup(); await screen.findByText("Account #42");
    await expectNoA11yViolations(screen.getByRole("region", { name: "Staff access" }));
  });
  it("shows server errors for failed access reads", async () => {
    request.mockRejectedValue(new Error("Access revoked")); setup();
    expect(await screen.findByRole("alert")).toHaveTextContent("Access revoked");
  });
});
