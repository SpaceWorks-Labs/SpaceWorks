import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlanUnitsField } from "./PlanUnitsField";

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

describe("PlanUnitsField (plan offered in units)", () => {
  it("shows sub-units as included through a ticked parent and saves only the ticked units", async () => {
    staffRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path.endsWith("/units") && init?.method === "PUT") return Promise.resolve(JSON.parse(String(init.body)));
      if (path.endsWith("/membership-plans/8/units")) return Promise.resolve({ unit_ids: [] });
      return Promise.resolve(tree);
    });
    wrap(<PlanUnitsField makerspaceId={4} planId={8} planName="Annual" />);
    expect(await screen.findByText("Offered in every unit. Tick units to limit it.")).toBeVisible();
    fireEvent.click(await screen.findByRole("checkbox", { name: /North/ }));
    expect(screen.getByRole("checkbox", { name: /Kochi/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Kochi/ })).toBeDisabled();
    expect(screen.getByText("Included through North")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Save units" }));
    expect(await screen.findByText("Plan units saved.")).toBeVisible();
    expect(sent("/membership-plans/8/units")).toEqual([{ unit_ids: [1] }]);
  });
});
