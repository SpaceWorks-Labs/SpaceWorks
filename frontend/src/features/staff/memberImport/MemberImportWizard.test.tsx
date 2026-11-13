import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MemberImportWizard } from "./MemberImportWizard";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const preview = {
  headers: ["Email", "Name"], mapping: { email: "Email", name: "Name" }, suggested_mapping: { email: "Email", name: "Name" },
  counts: { create: 1, update: 0, skip: 1 }, total_rows: 2,
  rows: [{ row: 2, action: "create", reason: "", data: { email: "a@example.test" } },
    { row: 3, action: "skip", reason: "email_invalid", data: { email: "bad" } }],
};
const result = { batch_id: 7, counts: { invited: 0, record_only: 1, updated: 0, skipped: 1 },
  rows: [{ row: 2, email: "a@example.test", action: "create", status: "record_only", reason: "" }] };

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation((path: string) => Promise.resolve(path.endsWith("/preview") ? preview : result));
});

describe("member import wizard (G18)", () => {
  it("maps, previews as a dry run, applies with staff choices and shows the result", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><MemberImportWizard makerspaceId={4} open onClose={vi.fn()} /></QueryClientProvider>);
    const file = new File(["Email,Name\na@example.test,A\n"], "members.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText("Member file"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText(/Dry run: 1 new, 0 updated, 1 skipped/)).toBeVisible();
    expect(screen.getByText("Email missing or invalid")).toBeVisible();
    fireEvent.click(screen.getByLabelText("Row 2 record only"));
    fireEvent.click(screen.getByRole("button", { name: "Import" }));
    expect(await screen.findByText("Import finished")).toBeVisible();
    const applied = staffRequest.mock.calls.find(([path]) => String(path).endsWith("/apply"));
    const body = applied![1].body as FormData;
    expect(body.get("record_only_rows")).toBe("[2]");
    expect(screen.getByRole("button", { name: "Download result CSV" })).toBeVisible();
    await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(2));
  });
});
