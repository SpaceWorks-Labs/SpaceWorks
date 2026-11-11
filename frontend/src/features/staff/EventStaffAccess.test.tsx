import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EventStaffAccess } from "./EventStaffAccess";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest: request }));
const grant = { id: 7, user: 42, permissions: ["check_in"], revoked_at: null };
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><EventStaffAccess target={{ kind: "event", id: 5 }} /></QueryClientProvider>);
  return client;
}
describe("event staff access management", () => {
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
    fireEvent.click(screen.getByLabelText("Check in attendees"));
    fireEvent.click(screen.getByRole("button", { name: "Invite staff" }));
    await screen.findByDisplayValue(/staff\/event-invite#token=secret-invitation-token/);
    expect(request).toHaveBeenCalledWith("/admin/events/5/staff-invites/", expect.objectContaining({ method: "POST",
      body: JSON.stringify({ email: "staff@example.test", send_email: true, permissions: ["check_in"] }) }));
    expect(JSON.stringify(client.getQueryCache().getAll().map((query) => query.state.data))).not.toContain("secret-invitation-token");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss link" }));
    expect(screen.queryByDisplayValue(/secret-invitation-token/)).not.toBeInTheDocument();
  });
  it("lets a full manager limit an invitation to a time window (decision 221(i))", async () => {
    setup(); await screen.findByText("Account #42");
    fireEvent.change(screen.getByLabelText("Invite email"), { target: { value: "staff@example.test" } });
    fireEvent.click(screen.getByLabelText("Check in attendees"));
    expect(screen.getByText("Leave these empty for access to every track at any time.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Valid until"), { target: { value: "2026-12-02T18:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Invite staff" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/events/5/staff-invites/", expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(String(request.mock.calls.find(([, init]) => init?.method === "POST")?.[1]?.body));
    expect(body).toEqual({ email: "staff@example.test", send_email: true, permissions: ["check_in"], valid_until: new Date("2026-12-02T18:00").toISOString() });
  });
  it("edits, invalidates and revokes grants", async () => {
    setup(); await screen.findByText("Account #42");
    fireEvent.click(screen.getByRole("button", { name: "Edit account #42" }));
    const fields = screen.getByRole("group", { name: "Permissions for account #42" });
    fireEvent.click(fields.querySelectorAll("input")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Save permissions" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/event-staff-grants/7/", expect.objectContaining({ method: "PATCH" })));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Save permissions" })).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Revoke account #42" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/event-staff-grants/7/revoke/", expect.objectContaining({ method: "POST" })));
  });
  it("shows server errors for failed access reads", async () => {
    request.mockRejectedValue(new Error("Access revoked")); setup();
    expect(await screen.findByRole("alert")).toHaveTextContent("Access revoked");
  });
});
