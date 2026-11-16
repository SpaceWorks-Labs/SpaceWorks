import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";

const staffRequest = vi.fn();
vi.mock("../../../lib/api", () => ({ staffRequest: (...args: unknown[]) => staffRequest(...args), staffRequestBlob: vi.fn() }));
vi.mock("./DeskBadgeFace", () => ({ deskSize: () => ({ widthMm: 100, heightMm: 150 }), DeskBadgeFace: () => null }));

import { BulkBadgesPanel } from "./BulkBadgesPanel";

function mount(canPrint = true) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><BulkBadgesPanel eventId={9} canPrint={canPrint} /></QueryClientProvider>);
}

it("starts a PDF job with the chosen status set and one badge per page", async () => {
  staffRequest.mockResolvedValue([]);
  mount();
  fireEvent.change(screen.getByLabelText("Who"), { target: { value: "crew" } });
  fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/events/9/card-jobs", expect.objectContaining({ method: "POST",
    body: JSON.stringify({ kind: "bulk_sheet", status_set: "crew", paper: "per_card" }) })));
});

it("warns that everyone prints provisional badges for waitlisted people", () => {
  staffRequest.mockResolvedValue([]);
  mount();
  fireEvent.change(screen.getByLabelText("Who"), { target: { value: "all" } });
  expect(screen.getByText(/provisional badges/)).toBeInTheDocument();
});

it("shows nothing without check-in permission", () => {
  staffRequest.mockResolvedValue([]);
  expect(mount(false).container).toBeEmptyDOMElement();
});
