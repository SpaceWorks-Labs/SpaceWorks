import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OrganizationReviewQueue } from "./OrganizationReviewQueue";
import type { ReviewQueueRow } from "./reviewApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest, publicV1Request: vi.fn() }));

const ROW: ReviewQueueRow = {
  id: 7, slug: "harbour-makers", name: "Harbour Makers", description: "A collective of boat builders.", website: "https://harbour.example",
  review_status: "pending_review", created_at: "2026-11-01T00:00:00Z", submitted_by: "mira",
};

function setup(rows: ReviewQueueRow[] = [ROW]) {
  staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") return { id: 7, review_status: "declined" };
    if (path === "/admin/organizations/7/review/") return [{ id: 1, action: "submitted", reason: "", created_at: "2026-11-01T00:00:00Z" }];
    const status = new URLSearchParams(path.split("?")[1]).get("status");
    const results = rows.filter(row => row.review_status === status);
    return { count: results.length, next: null, previous: null, results };
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><OrganizationReviewQueue /></QueryClientProvider>);
}

async function openDrawer(name = "Harbour Makers") {
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(name) }));
  return screen.findByRole("dialog", { name });
}

const posted = () => {
  const call = staffRequest.mock.calls.find(row => (row[1] as RequestInit | undefined)?.method === "POST");
  return call ? { path: call[0], body: JSON.parse((call[1] as RequestInit).body as string), context: call[2] } : undefined;
};

beforeEach(() => { staffRequest.mockReset(); });

describe("OrganizationReviewQueue", () => {
  it("opens on organizations waiting for review, through the platform session", async () => {
    setup();
    expect(await screen.findByText("Harbour Makers")).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/organization-reviews/?status=pending_review&page=1", {}, "platform");
  });

  it("filters by standing and says plainly when nothing matches", async () => {
    setup();
    await screen.findByText("Harbour Makers");
    fireEvent.change(screen.getByRole("combobox", { name: "Status" }), { target: { value: "suspended" } });
    expect(await screen.findByText("No organization is suspended.")).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/organization-reviews/?status=suspended&page=1", {}, "platform");
  });

  it("shows the application, its history and only the decisions open to a pending organization", async () => {
    setup();
    const drawer = await openDrawer();
    expect(within(drawer).getByText("A collective of boat builders.")).toBeInTheDocument();
    expect(await within(drawer).findByText(/Submitted for review/)).toBeInTheDocument();
    for (const label of ["Approve…", "Request changes…", "Decline…"]) expect(within(drawer).getByRole("button", { name: label })).toBeInTheDocument();
    expect(within(drawer).queryByRole("button", { name: "Suspend…" })).toBeNull();
    expect(staffRequest).toHaveBeenCalledWith("/admin/organizations/7/review/", {}, "platform");
  });

  it("will not decline without a reason, then sends the decision with it", async () => {
    setup();
    const drawer = await openDrawer();
    fireEvent.click(within(drawer).getByRole("button", { name: "Decline…" }));
    const dialog = await screen.findByRole("dialog", { name: "Decline Harbour Makers?" });
    const confirm = within(dialog).getByRole("button", { name: "Decline" });
    expect(confirm).toBeDisabled();
    expect(within(dialog).getByText(/confirm it's you/)).toBeInTheDocument();
    fireEvent.change(within(dialog).getByRole("textbox", { name: /Reason/ }), { target: { value: "Duplicate of an existing organization." } });
    fireEvent.click(confirm);
    await waitFor(() => expect(posted()).toEqual({ path: "/admin/organizations/7/review/",
      body: { decision: "decline", reason: "Duplicate of an existing organization." }, context: "platform" }));
  });

  it("approves without a reason", async () => {
    setup();
    const drawer = await openDrawer();
    fireEvent.click(within(drawer).getByRole("button", { name: "Approve…" }));
    const dialog = await screen.findByRole("dialog", { name: "Approve Harbour Makers?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(posted()?.body).toEqual({ decision: "approve", reason: "" }));
  });

  it("offers only suspension for an approved organization", async () => {
    setup([{ ...ROW, review_status: "approved" }]);
    fireEvent.change(await screen.findByRole("combobox", { name: "Status" }), { target: { value: "approved" } });
    const drawer = await openDrawer();
    expect(within(drawer).getByRole("button", { name: "Suspend…" })).toBeInTheDocument();
    expect(within(drawer).queryByRole("button", { name: "Approve…" })).toBeNull();
  });
});
