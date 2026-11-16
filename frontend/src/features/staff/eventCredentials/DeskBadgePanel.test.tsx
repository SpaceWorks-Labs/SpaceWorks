import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import fixture from "../../../../../backend/tests/events/programme/contracts/fixtures/template-seed-v2.json";
import { DeskBadgePanel } from "./DeskBadgePanel";

const mocks = vi.hoisted(() => ({ request: vi.fn(), blob: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: mocks.request, staffRequestBlob: mocks.blob }));
beforeEach(() => {
  mocks.request.mockReset(); mocks.blob.mockReset();
  mocks.request.mockImplementation((path: string) => {
    if (path.includes("desk-design")) return Promise.resolve({ id: 3, document: fixture.badge_seed.document, stock: "cr80-landscape", event_version: 4 });
    if (path.includes("print-jobs")) return Promise.resolve({ job_id: 9, state: "ready", status_url: "/status/9" });
    return Promise.resolve({ results: [] });
  });
  mocks.blob.mockResolvedValue(new Blob(["pdf"], { type: "application/pdf" }));
  vi.stubGlobal("URL", class extends URL { static createObjectURL() { return "blob:test"; } static revokeObjectURL() {} });
});

function show(canEdit = false) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <DeskBadgePanel eventId={42} eventVersion={4} registrationIds={[71]} canEdit={canEdit} canPrint />
  </QueryClientProvider>);
}

it("lets a check-in operator use the saved design without edit permission or loading the design catalogue", async () => {
  show();
  // The saved design loads before Prepare enables; allow for a loaded full-suite shard (it timed out at 1 s there).
  await waitFor(() => expect(screen.getByRole("button", { name: /Prepare 1 ID cards/ })).toBeEnabled(), { timeout: 5000 });
  expect(mocks.request.mock.calls.every((row) => !row[0].includes("designs/?"))).toBe(true);
  expect(screen.queryByRole("button", { name: "Validate and save design" })).not.toBeInTheDocument();
});

it("requests a private job with photos off and uses its authenticated download gateway", async () => {
  show(); const button = screen.getByRole("button", { name: /Prepare 1 ID cards/ });
  await waitFor(() => expect(button).toBeEnabled()); fireEvent.click(button);
  await waitFor(() => expect(mocks.blob).toHaveBeenCalledWith("/admin/events/42/badges/print-jobs/9/download/", expect.objectContaining({ signal: expect.any(AbortSignal) })));
  const call = mocks.request.mock.calls.find((row) => row[1]?.method === "POST")!;
  expect(JSON.parse(call[1].body)).toMatchObject({ registration_ids: [71], expected_version: 4, template_revision: 3, include_photo: false });
});
