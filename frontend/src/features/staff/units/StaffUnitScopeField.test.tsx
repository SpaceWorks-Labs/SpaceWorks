import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { StaffUnitScopeField } from "./StaffUnitScopeField";

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
const sent = (suffix: string) => staffRequest.mock.calls.filter(([path, init]) => String(path).endsWith(suffix) && init?.method === "PUT")
  .map(([, init]) => JSON.parse(String(init.body)));

beforeEach(() => { staffRequest.mockReset(); });

describe("StaffUnitScopeField (unit-scoped staff)", () => {
  it("is absent while unit-scoped staff is off", async () => {
    staffRequest.mockImplementation(() => Promise.reject(new StructuredApiError(404, { code: "feature_disabled", detail: "off" })));
    const { container } = wrap(<StaffUnitScopeField makerspaceId={4} membershipId={11} name="Asha" />);
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("limits a staff member to a unit and lifts the limit again", async () => {
    staffRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path.endsWith("/unit-scope") && init?.method === "PUT") {
        const id = JSON.parse(String(init.body)).unit_id;
        return Promise.resolve({ membership_id: 11, unit: id ? tree.units.find(row => row.id === id) : null });
      }
      if (path.endsWith("/unit-scope")) return Promise.resolve({ membership_id: 11, unit: null });
      return Promise.resolve(tree);
    });
    wrap(<StaffUnitScopeField makerspaceId={4} membershipId={11} name="Asha" />);
    const picker = await screen.findByRole("combobox", { name: "Limited to" });
    await screen.findByRole("option", { name: /Kochi/ });
    fireEvent.change(picker, { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Save unit limit" }));
    expect(await screen.findByText("Asha now works only with Kochi.")).toBeVisible();
    fireEvent.change(picker, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save unit limit" }));
    expect(await screen.findByText("Asha works with the whole space again.")).toBeVisible();
    expect(sent("/staff/11/unit-scope")).toEqual([{ unit_id: 2 }, { unit_id: null }]);
  });
});
