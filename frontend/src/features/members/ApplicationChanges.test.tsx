import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError, memberRequest } from "../../lib/api";
import { MemberAdmission } from "./MemberAdmission";
import { admissionStateLabel } from "./membershipLabels";
import type { AdmissionRequest } from "./membershipAdmissionApi";

vi.mock("../../lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("../../lib/api")>()), memberRequest: vi.fn() }));

function show(request: AdmissionRequest) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["member", "memberships"], {});
  render(<QueryClientProvider client={client}><MemberAdmission makerspaceId={7} request={request} /></QueryClientProvider>);
  return client;
}

const sentBack: AdmissionRequest = {
  id: 21, state: "changes_requested", expires_at: "2026-12-01T12:00:00Z",
  changes_note: "Please say which machines you want to use.", changes_rounds: 1,
  application_answers: { version: 1, answers: [{ id: "why", label: "Why join?", type: "short_text", value: "To make things" }] },
  edit_schema: [{ id: "why", label: "Why join?", type: "short_text", options: [], required: true }],
  join_fields: { photo: "off", phone: "required", state: "hidden" },
};

beforeEach(() => { vi.mocked(memberRequest).mockReset(); });

describe("the applicant's changes loop (parity O-B2)", () => {
  it("shows the reviewer's note and resubmits edited answers once", async () => {
    vi.mocked(memberRequest).mockResolvedValue({ id: 21, state: "requested" });
    const client = show(sentBack);
    expect(screen.getByRole("heading", { name: "Your application needs changes" })).toBeVisible();
    expect(screen.getByText(/Please say which machines you want to use\./)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Edit my application/ }));
    const answer = screen.getByDisplayValue("To make things");
    fireEvent.change(answer, { target: { value: "The laser cutter and the 3D printers" } });
    fireEvent.change(screen.getByLabelText(/Phone number/), { target: { value: "98765 43210" } });
    fireEvent.click(screen.getByRole("button", { name: "Send my application back" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/memberships/requests/21", {
      method: "PATCH",
      body: JSON.stringify({ application_answers: { why: "The laser cutter and the 3D printers" }, join_fields: { phone: "+919876543210" } }),
    }));
    await waitFor(() => expect(client.getQueryState(["member", "memberships"])?.isInvalidated).toBe(true));
  });

  it("lets a phone already on file stay blank, and shows a server refusal", async () => {
    vi.mocked(memberRequest).mockRejectedValue(new StructuredApiError(400, { code: "membership_request_expired", detail: "This membership application has expired." }));
    show(sentBack);
    fireEvent.click(screen.getByRole("button", { name: /Edit my application/ }));
    expect(screen.getByText("Leave blank to keep the number you gave before, if any.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Send my application back" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This membership application has expired.");
    expect(memberRequest).toHaveBeenCalledWith("/memberships/requests/21", expect.objectContaining({ method: "PATCH" }));
  });

  it("names the state and allows cancelling while changes are pending", () => {
    show(sentBack);
    expect(admissionStateLabel("changes_requested")).toBe("Changes requested");
    expect(screen.getByRole("button", { name: "Cancel application" })).toBeEnabled();
  });
});
