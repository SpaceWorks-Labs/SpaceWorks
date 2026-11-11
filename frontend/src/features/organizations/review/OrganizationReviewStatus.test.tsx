import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OrganizationReviewStatus } from "./OrganizationReviewStatus";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest, publicV1Request: vi.fn() }));

const GOVERNOR = ["manage_organization_members", "manage_organization_profile"];
const HISTORY = [
  { id: 2, action: "changes_requested", reason: "Add a website and a short description.", created_at: "2026-11-03T00:00:00Z" },
  { id: 1, action: "submitted", reason: "", created_at: "2026-11-01T00:00:00Z" },
];

function show(review_status: string, governance_actions = GOVERNOR) {
  staffRequest.mockImplementation(async (_path: string, init?: RequestInit) => init?.method === "POST" ? { id: 5, review_status: "pending_review" } : HISTORY);
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <OrganizationReviewStatus organization={{ id: 5, name: "Harbour Makers", review_status, governance_actions }} />
  </QueryClientProvider>);
}

beforeEach(() => { staffRequest.mockReset(); });

describe("OrganizationReviewStatus", () => {
  it("renders nothing for an approved organization and never asks for its history", () => {
    const { container } = show("approved");
    expect(container).toBeEmptyDOMElement();
    expect(staffRequest).not.toHaveBeenCalled();
  });

  it("explains that a pending organization is inert until approved", async () => {
    show("pending_review");
    expect(screen.getByRole("heading", { name: "Waiting for platform review" })).toBeInTheDocument();
    expect(screen.getByText(/no public page, space links or invitations yet/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resubmit for review" })).toBeNull();
    expect(await screen.findByText("Submitted for review", { exact: false })).toBeInTheDocument();
  });

  it("shows the reviewer's note and resubmits with the applicant's own note", async () => {
    show("changes_requested");
    expect((await screen.findAllByText("Add a website and a short description.")).length).toBeGreaterThan(0);
    fireEvent.change(screen.getByRole("textbox", { name: /Note for the reviewer/ }), { target: { value: "Added both." } });
    fireEvent.click(screen.getByRole("button", { name: "Resubmit for review" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/organizations/5/resubmit/",
      { method: "POST", body: JSON.stringify({ note: "Added both." }) }));
  });

  it("keeps notes and resubmission to profile governors", () => {
    show("changes_requested", ["manage_organization_members"]);
    expect(screen.getByRole("heading", { name: "Changes requested" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resubmit for review" })).toBeNull();
    expect(screen.getByText(/profile rights can see the reviewer's notes/)).toBeInTheDocument();
    expect(staffRequest).not.toHaveBeenCalled();
  });

  it("tells a declined applicant the address is held for 30 days", () => {
    show("declined");
    expect(screen.getByRole("heading", { name: "Application declined" })).toBeInTheDocument();
    expect(screen.getByText(/stays reserved for 30 days/)).toBeInTheDocument();
  });
});
