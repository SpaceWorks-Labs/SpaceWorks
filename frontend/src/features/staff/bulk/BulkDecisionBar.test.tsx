import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api/errors";
import { BulkDecisionBar } from "./BulkDecisionBar";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...await original<typeof import("../../../lib/api")>(), staffRequest }));

const rows = Array.from({ length: 55 }, (_, index) => ({ id: index + 1, label: `Request ${index + 1}` }));
const decisions = [{ key: "accept", label: "Accept" }, { key: "reject", label: "Reject", needsReason: true, danger: true }];
const mount = (onDone = vi.fn(), list = rows) => render(<QueryClientProvider client={new QueryClient()}>
  <BulkDecisionBar title="Decide several" rows={list} decisions={decisions} path={decision => `/admin/bulk/requests/${decision}`} onDone={onDone} />
</QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

describe("decision 242 / U5: bulk decisions", () => {
  it("selects at most 50 and posts the ids with the reason", async () => {
    const done = vi.fn();
    staffRequest.mockResolvedValue({ decided: 50, ids: [] });
    mount(done);
    fireEvent.click(screen.getByRole("button", { name: "Decide several at once" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Select the first 50" }));
    expect(screen.getByRole("checkbox", { name: "Request 51" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject (50)" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "Out of season" } });
    fireEvent.click(screen.getByRole("button", { name: "Reject (50)" }));
    await waitFor(() => expect(done).toHaveBeenCalled());
    const [path, init] = staffRequest.mock.calls[0];
    expect(path).toBe("/admin/bulk/requests/reject");
    expect(JSON.parse(init.body)).toEqual({ ids: rows.slice(0, 50).map(row => row.id), reason: "Out of season" });
  });

  it("names the row that stopped an all-or-nothing batch on a 409", async () => {
    staffRequest.mockImplementation(() => Promise.reject(new StructuredApiError(409, { detail: "Nothing was changed", code: "bulk_failed", failed_id: 2,
      cause: { detail: "Request is no longer pending." } })));
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Decide several at once" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Request 1" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Request 2" }));
    fireEvent.click(screen.getByRole("button", { name: "Accept (2)" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Nothing was changed. Request 2 could not be decided: Request is no longer pending.");
  });

  it("stays out of the way with fewer than two waiting rows", () => {
    mount(vi.fn(), rows.slice(0, 1));
    expect(screen.queryByRole("button", { name: "Decide several at once" })).toBeNull();
  });
});
