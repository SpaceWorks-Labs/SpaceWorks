import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OnboardingSection } from "./OnboardingSection";
import type { HostingRequestDetail } from "./onboardingApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest, publicV1Request: vi.fn() }));

const base: HostingRequestDetail = {
  id: 4, status: "submitted", source: "public", space_name: "Harbour Works", proposed_slug: "harbour", location: "Kochi",
  expected_members: null, applicant_name: "Mira", applicant_email: "mira@example.com", applicant_phone: "", space_website_url: "",
  description: "A waterfront workshop.", organization_choice: "own", new_organization_name: "", inviter_summary: "",
  created_at: "2026-11-01T00:00:00Z", verified_at: null, decided_at: null, changes_note: "", created_makerspace: null, revisions: [],
};
const ORG: HostingRequestDetail = { ...base, id: 5, space_name: "Chess Society", location: "", requested_kind: "organization",
  description: "A city chess society." };

function setup(rows: HostingRequestDetail[]) {
  staffRequest.mockImplementation(async (path: string) => {
    const detail = rows.find(row => path === `/admin/platform/hosting-requests/${row.id}`);
    return detail ?? { count: rows.length, next: null, previous: null, results: rows };
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><OnboardingSection /></QueryClientProvider>);
}

beforeEach(() => staffRequest.mockReset());

describe("hosting request kinds in the platform console (decision 295)", () => {
  it("shows each request's kind and filters by requested_kind", async () => {
    setup([base, ORG]);
    expect(await screen.findByText(/Organization · Mira/)).toBeInTheDocument();
    expect(screen.getByText(/Makerspace · Mira · Kochi/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "organization" } });
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(
      "/admin/platform/hosting-requests?status=submitted&requested_kind=organization&page=1", {}, "platform"));
    // Rows of the other kind never show, even from a server that ignores the filter.
    expect(screen.queryByRole("button", { name: /Harbour Works/ })).not.toBeInTheDocument();
  });

  it("approves an organization request from the console, like a makerspace one", async () => {
    setup([ORG]);
    fireEvent.click(await screen.findByRole("button", { name: /Chess Society/ }));
    const drawer = await screen.findByRole("dialog", { name: "Chess Society" });
    expect(within(drawer).getByRole("button", { name: "Approve…" })).toBeInTheDocument();
    expect(within(drawer).queryByRole("link", { name: /Approve in \/control\// })).not.toBeInTheDocument();
    expect(within(drawer).getByText("About the organization")).toBeInTheDocument();
    expect(within(drawer).getAllByText("Not given").length).toBeGreaterThan(1);
  });

  it("keeps console approval for makerspace requests", async () => {
    setup([base]);
    fireEvent.click(await screen.findByRole("button", { name: /Harbour Works/ }));
    const drawer = await screen.findByRole("dialog", { name: "Harbour Works" });
    expect(within(drawer).getByRole("button", { name: "Approve…" })).toBeInTheDocument();
  });
});
