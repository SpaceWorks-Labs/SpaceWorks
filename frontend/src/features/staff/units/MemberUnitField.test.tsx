import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { MemberUnitField } from "./MemberUnitField";

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

describe("MemberUnitField (a member's unit)", () => {
  it("moves a member into a unit and explains a refusal outside the caller's unit", async () => {
    let refuse = false;
    staffRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path.endsWith("/memberships/21/unit") && init?.method === "PUT") {
        if (refuse) return Promise.reject(new StructuredApiError(400, { code: "unit_scope_forbids", detail: "server" }));
        return Promise.resolve({ membership_id: 21, unit: tree.units[2] });
      }
      if (path.endsWith("/memberships/21/unit")) return Promise.resolve({ membership_id: 21, unit: tree.units[1] });
      return Promise.resolve(tree);
    });
    wrap(<MemberUnitField makerspaceId={4} membershipId={21} />);
    const picker = await screen.findByRole("combobox", { name: "Unit" });
    await waitFor(() => expect(picker).toHaveValue("2"));
    fireEvent.change(picker, { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Save unit" }));
    expect(await screen.findByText("Now in South.")).toBeVisible();
    expect(sent("/memberships/21/unit")).toEqual([{ unit_id: 3 }]);
    refuse = true;
    fireEvent.change(picker, { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Save unit" }));
    expect(await screen.findByText("Your role is limited to one unit, so you can't change this.")).toBeVisible();
  });

  it("is absent while member units are off", async () => {
    staffRequest.mockImplementation(() => Promise.reject(new StructuredApiError(404, { code: "feature_disabled", detail: "off" })));
    const { container } = wrap(<MemberUnitField makerspaceId={4} membershipId={21} />);
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
