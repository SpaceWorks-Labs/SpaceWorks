import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";
import { PartnerEvents } from "./PartnerEvents";

const { staffRequest, tenantMemberRequest } = vi.hoisted(() => ({
  staffRequest: vi.fn(), tenantMemberRequest: vi.fn(),
}));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual("../../lib/api"),
  staffRequest, tenantMemberRequest,
}));
const event = {
  id: 4, title: "Private partner workshop", starts_at: "2026-11-01T10:00:00Z",
  ends_at: "2026-11-01T12:00:00Z", host_name: "Host", host_slug: "host",
  registration_open: false, registration_requires_approval: true,
  effective_registration_cutoff_at: "2026-10-14T12:00:00Z", series: null,
  registration_audience: "participating_organizations", consent_repair_required: true,
  host_waiver: { id: 3, version: "v2", body: "Renewed private host terms" },
  custom_form: [{ id: "reason", type: "short_text", label: "Reason", required: true }],
  ticket_selection_required: true, ticket_types: [], promo_codes_enabled: true,
};
const registrationPath = "/member/makerspaces/2/collaborative-events/4/register/";
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><PartnerEvents makerspaceId={2} slug="partner" /></QueryClientProvider>);
  return { client, invalidate };
}
beforeEach(() => { vi.clearAllMocks(); staffRequest.mockReset(); });

describe("closed private partner consent renewal", () => {
  it("submits only explicit consent through the partner route and refreshes partner state", async () => {
    staffRequest.mockImplementation((_path, options) => Promise.resolve(options?.method === "POST"
      ? { registration_id: 8, status: "pending_approval" } : [event]));
    const { client, invalidate } = show();
    expect(await screen.findByRole("button", { name: "Registration closed" })).toBeDisabled();
    expect(await screen.findByText("Renewed private host terms")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save consent" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Accept the current host waiver.");
    expect(staffRequest.mock.calls.filter(([, options]) => options?.method === "POST")).toHaveLength(0);
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Save consent" }));
    await screen.findByText("Your registration consent has been updated.");
    expect(staffRequest).toHaveBeenCalledWith(registrationPath, {
      method: "POST", body: JSON.stringify({ host_waiver_id: 3, host_waiver_version: "v2", host_waiver_accepted: true }),
    });
    expect(tenantMemberRequest).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("Reason")).not.toBeInTheDocument();
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["member", "partner", "activity"] }));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["member", "partner", "partner-events"] });
    client.clear();
  });

  it("requires fresh acceptance when the host publishes a new waiver during renewal", async () => {
    let latest = event;
    staffRequest.mockImplementation((_path, options) => {
      if (options?.method !== "POST") return Promise.resolve([latest]);
      latest = { ...event, host_waiver: { id: 5, version: "v3", body: "Third host terms" } };
      return Promise.reject(new StructuredApiError(400, { code: "host_waiver_required", detail: "Accept current terms." }));
    });
    const { client } = show();
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Save consent" }));
    await screen.findByText("Third host terms");
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Save consent" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Accept the current host waiver.");
    expect(staffRequest.mock.calls.filter(([, options]) => options?.method === "POST")).toHaveLength(1);
    client.clear();
  });

  it("shows a policy refusal without reporting successful renewal", async () => {
    staffRequest.mockImplementation((_path, options) => options?.method === "POST"
      ? Promise.reject(new StructuredApiError(403, { detail: "Active organization membership is required." }))
      : Promise.resolve([event]));
    const { client } = show();
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Save consent" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Active organization membership is required.");
    expect(screen.queryByText("Your registration consent has been updated.")).not.toBeInTheDocument();
    client.clear();
  });

  it("keeps closed signup disabled without offering repair for accounts lacking an owned stale live row", async () => {
    staffRequest.mockResolvedValue([{ ...event, consent_repair_required: false }]);
    const { client } = show();
    expect(await screen.findByRole("button", { name: "Registration closed" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save consent" })).not.toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledTimes(1);
    client.clear();
  });
});
