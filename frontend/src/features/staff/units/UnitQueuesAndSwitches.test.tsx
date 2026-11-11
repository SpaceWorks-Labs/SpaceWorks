import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { ImportReviewQueue } from "./ImportReviewQueue";
import { ImportUnitFields, appendImportUnit } from "./ImportUnitFields";
import { UnitSwitchesSettings } from "./UnitSwitchesSettings";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{node}</QueryClientProvider>);
const unit = (id: number, parent: number | null, name: string, path: string, level: number) => ({
  id, parent_id: parent, name, slug: name, code: name.toUpperCase().slice(0, 6), level, level_name: "", path, sort_order: 0,
  archived: false, has_payment_instructions: false });
const tree = { levels: [], templates: [], limit: null, used: 3, scoped: false,
  units: [unit(1, null, "North", "/NORTH/", 0), unit(2, 1, "Kochi", "/NORTH/KOCHI/", 1), unit(3, null, "South", "/SOUTH/", 0)] };

beforeEach(() => { staffRequest.mockReset(); });

describe("import review queue (verify mode)", () => {
  it("approves and rejects held rows for the unit lead", async () => {
    staffRequest.mockImplementation((path: string) => {
      if (path.endsWith("/member-import-reviews")) return Promise.resolve([
        { id: 40, unit_id: 2, review_status: "pending", row_status: "pending", name: "Ravi", email: "ravi@example.test", created_at: "2026-11-01T10:00:00Z" },
        { id: 41, unit_id: 2, review_status: "pending", row_status: "pending", name: "***", email: "***", created_at: "2026-11-01T10:00:00Z" }]);
      if (path.includes("/member-import-reviews/")) return Promise.resolve({ id: 40, review_status: "approved" });
      return Promise.resolve(tree);
    });
    wrap(<ImportReviewQueue makerspaceId={4} />);
    expect(await screen.findByText("Ravi")).toBeVisible();
    expect(await screen.findByText(/ravi@example\.test · Kochi/)).toBeVisible();
    fireEvent.click(screen.getAllByRole("button", { name: "Approve" })[0]);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/member-import-reviews/40/approve", { method: "POST" }));
    fireEvent.click(screen.getAllByRole("button", { name: "Reject" })[1]);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/member-import-reviews/41/reject", { method: "POST" }));
  });

  it("says when nothing is waiting, and disappears while units are off", async () => {
    staffRequest.mockImplementation((path: string) => Promise.resolve(path.endsWith("/member-import-reviews") ? [] : tree));
    const { unmount } = wrap(<ImportReviewQueue makerspaceId={4} />);
    expect(await screen.findByText("Nothing waiting for review.")).toBeVisible();
    unmount();
    staffRequest.mockImplementation(() => Promise.reject(new StructuredApiError(404, { code: "feature_disabled", detail: "off" })));
    const { container } = wrap(<ImportReviewQueue makerspaceId={4} />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});

describe("import unit options", () => {
  it("sends the unit and verify mode only when a unit is chosen", async () => {
    staffRequest.mockResolvedValue(tree);
    const onChange = vi.fn();
    wrap(<ImportUnitFields makerspaceId={4} value={{ unitId: null, verify: false }} onChange={onChange} />);
    expect(screen.getByRole("checkbox", { name: /approve each row first/ })).toBeDisabled();
    await screen.findByRole("option", { name: /Kochi/ });
    fireEvent.change(screen.getByRole("combobox", { name: "Put everyone in" }), { target: { value: "2" } });
    expect(onChange).toHaveBeenCalledWith({ unitId: 2, verify: false });
    expect([...appendImportUnit(new FormData(), { unitId: null, verify: true }).keys()]).toEqual([]);
    const body = appendImportUnit(new FormData(), { unitId: 2, verify: true });
    expect([body.get("unit_id"), body.get("verify")]).toEqual(["2", "true"]);
  });
});

describe("Settings â€º People â€º Member units switches", () => {
  it("offers unit-scoped staff only with units on, and turns both off together", async () => {
    staffRequest.mockResolvedValue({});
    const { rerender } = wrap(<UnitSwitchesSettings space={{ id: 4, enabled_features: ["membership.titles"] }} />);
    expect(screen.queryByRole("checkbox", { name: "Allow unit limits on staff" })).toBeNull();
    fireEvent.click(screen.getByRole("checkbox", { name: "Use member units" }));
    await waitFor(() => expect(JSON.parse(String(staffRequest.mock.calls[0][1].body))).toEqual({ enabled_features: ["membership.titles", "membership.units"] }));
    rerender(<QueryClientProvider client={new QueryClient()}><UnitSwitchesSettings space={{ id: 4, enabled_features: ["membership.units", "membership.unit_scoped_staff"] }} /></QueryClientProvider>);
    expect(screen.getByRole("checkbox", { name: "Allow unit limits on staff" })).toBeChecked();
    fireEvent.click(screen.getByRole("checkbox", { name: "Use member units" }));
    await waitFor(() => expect(JSON.parse(String(staffRequest.mock.calls[1][1].body))).toEqual({ enabled_features: [] }));
  });
});
