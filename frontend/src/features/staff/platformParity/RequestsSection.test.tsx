import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { RequestsSection } from "./RequestsSection";

vi.mock("../../../lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));
const request = vi.mocked(staffRequest);

const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results });
const archive = { id: 1, makerspace: 2, makerspace_name: "North Lab", status: "pending", reason: "Closing down", resolution_note: "",
  requested_at: "2026-11-01T10:00:00Z", resolved_at: null };
const apiKey = { id: 5, makerspace: 2, makerspace_name: "North Lab", label: "Kiosk", reason: "", allowed_origins: ["https://kiosk.example.org"],
  status: "pending", created_at: "2026-11-02T10:00:00Z", resolved_at: null };
const subdomain = { id: 9, makerspace: 3, makerspace_name: "South Lab", requested_label: "south", status: "pending",
  created_at: "2026-11-03T10:00:00Z", decided_at: null };

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><RequestsSection /></QueryClientProvider>);
}

describe("RequestsSection", () => {
  beforeEach(() => {
    request.mockReset();
    request.mockImplementation(async (path, init) => {
      if (path === "/admin/platform/api-key-requests/5/approve") return { request: { ...apiKey, status: "approved" }, client_id: "cid-1", client_secret: "s3cret-once" } as never;
      if (init?.method === "POST") return archive as never;
      if (path.startsWith("/admin/platform/archive-requests")) return page([archive]) as never;
      if (path.startsWith("/admin/platform/api-key-requests")) return page([apiKey]) as never;
      return page([subdomain]) as never;
    });
  });

  it("lists pending requests from all three queues", async () => {
    renderSection();
    expect(await screen.findByText("Kiosk")).toBeInTheDocument();
    expect(await screen.findByText("south")).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/admin/platform/archive-requests?page=1&status=pending", {}, "platform");
  });

  it("needs a note to decline an archive request", async () => {
    renderSection();
    fireEvent.click(await screen.findByRole("button", { name: "Decline the archive request of North Lab" }));
    const confirm = screen.getByRole("button", { name: "Decline request" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox", { name: "Note" }), { target: { value: "Talk to us first" } });
    fireEvent.click(confirm);
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/archive-requests/1/decline",
      { method: "POST", body: JSON.stringify({ note: "Talk to us first" }) }, "platform"));
  });

  it("shows an approved API key's secret once", async () => {
    renderSection();
    fireEvent.click(await screen.findByRole("button", { name: 'Approve the API key "Kiosk" for North Lab' }));
    fireEvent.click(screen.getByRole("button", { name: "Approve and issue key" }));
    expect(await screen.findByText("s3cret-once")).toBeInTheDocument();
    expect(screen.getByText("Copy it now; it cannot be shown again.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    await waitFor(() => expect(screen.queryByText("s3cret-once")).not.toBeInTheDocument());
  });
});
