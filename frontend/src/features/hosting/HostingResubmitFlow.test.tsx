import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { publicV1Request } from "../../lib/api";
import { HostingResubmitFlow } from "./HostingResubmitFlow";

vi.mock("../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../lib/api")>(), publicV1Request: vi.fn() }));
beforeEach(() => { vi.mocked(publicV1Request).mockReset(); });

it("edits, reviews and resubmits with the link token and the reviewer note", async () => {
  vi.mocked(publicV1Request).mockResolvedValue({ status: "submitted", space_name: "New name" });
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>
    <HostingResubmitFlow token="tok" onDone={() => {}} request={{ status: "changes_requested", space_name: "Old name", created_at: "2026-10-01T00:00:00Z",
      verified_at: null, decided_at: null, rejection_reason: null, changes_note: "Add opening hours", editable: true,
      location: "Kochi", description: "A community workshop for everyone.", revisions: [], space_website_url: "", proposed_slug: "", new_organization_name: "" }} />
  </MemoryRouter></QueryClientProvider>);
  expect(screen.getByText("Add opening hours")).toBeVisible();
  fireEvent.change(screen.getByLabelText("Makerspace name"), { target: { value: "New name" } });
  fireEvent.click(screen.getByRole("button", { name: "Review changes" }));
  expect(screen.getByText("New name")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Send for review" }));
  await waitFor(() => expect(publicV1Request).toHaveBeenCalled());
  const [path, options] = vi.mocked(publicV1Request).mock.calls[0];
  expect(path).toBe("/public/hosting/requests/resubmit");
  expect(JSON.parse(String(options?.body))).toMatchObject({ token: "tok", space_name: "New name", location: "Kochi" });
  expect(await screen.findByText("Sent back for review")).toBeVisible();
});
