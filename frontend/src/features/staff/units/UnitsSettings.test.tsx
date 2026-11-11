import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { UnitsSettings } from "./UnitsSettings";
import type { MemberUnit, MemberUnitList } from "./unitsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const unit = (id: number, parent: number | null, name: string, code: string, path: string, level: number): MemberUnit => ({
  id, parent_id: parent, name, slug: name.toLowerCase(), code, level, level_name: ["District", "Chapter"][level] ?? "",
  path, sort_order: 0, archived: false, has_payment_instructions: false,
});
const templates = [{ key: "area_unit", label: "Area and unit", levels: ["Area", "Unit"] },
  { key: "state_district_chapter", label: "State, district and chapter", levels: ["State", "District", "Chapter"] },
  { key: "branches", label: "Branches only", levels: ["Branch"] }];
const north = unit(1, null, "North", "NORTH", "/NORTH/", 0);
const kochi = unit(2, 1, "Kochi", "KOCHI", "/NORTH/KOCHI/", 1);
const south = unit(3, null, "South", "SOUTH", "/SOUTH/", 0);
let list: MemberUnitList;

const renderIt = (canManage = true) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
  <UnitsSettings makerspaceId={7} canManage={canManage} /></QueryClientProvider>);
const calls = (suffix: string) => staffRequest.mock.calls.filter(([path, init]) => String(path).endsWith(suffix) && init?.method);

beforeEach(() => {
  list = { levels: ["District", "Chapter"], templates, units: [kochi, south, north], limit: null, used: 3, scoped: false };
  staffRequest.mockReset();
  staffRequest.mockImplementation((path: string, init?: RequestInit) => {
    if (path.endsWith("/member-units") && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      return Promise.resolve({ ...unit(9, body.parent_id, body.name, "EAST", "/EAST/", 0), payment_instructions: "", effective_payment_instructions: "", effective_instructions_unit_id: null });
    }
    if (path.includes("/member-units?") || path.endsWith("/member-units")) return Promise.resolve(list);
    return Promise.resolve({});
  });
});

describe("member units tree editor (parity O-F1)", () => {
  it("shows the tree in order with codes and level names, and creates a top-level unit", async () => {
    renderIt();
    const tree = await screen.findByRole("list", { name: "Member units" });
    expect(within(tree).getAllByRole("listitem").map(item => item.textContent)).toEqual([
      expect.stringContaining("North"), expect.stringContaining("Kochi"), expect.stringContaining("South")]);
    expect(within(tree).getByText("KOCHI")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Add District" }));
    fireEvent.change(await screen.findByLabelText("Name"), { target: { value: "East" } });
    fireEvent.click(screen.getByRole("button", { name: "Add unit" }));
    expect(await screen.findByText("East added with code EAST.")).toBeVisible();
    expect(JSON.parse(String(calls("/member-units")[0][1].body))).toEqual({ name: "East", sort_order: 0, payment_instructions: "", parent_id: null });
  });

  it("archives a unit after confirming, and refuses one with units beneath it", async () => {
    renderIt();
    fireEvent.click(await screen.findByRole("button", { name: "Actions for North" }));
    expect(screen.getByRole("menuitem", { name: /Archive/ })).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(screen.getByRole("button", { name: "Actions for South" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Archive" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Archive" }));
    await waitFor(() => expect(calls("/member-units/3/archive")).toHaveLength(1));
  });

  it("explains a refused move in plain words", async () => {
    staffRequest.mockImplementation((path: string) => path.endsWith("/move")
      ? Promise.reject(new StructuredApiError(400, { code: "member_unit_depth", detail: "server text" }))
      : Promise.resolve(list));
    renderIt();
    fireEvent.click(await screen.findByRole("button", { name: "Actions for South" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Move…" }));
    const dialog = await screen.findByRole("dialog");
    const picker = within(dialog).getByRole("combobox");
    // Kochi sits on the deepest named level, so it is offered disabled.
    expect(within(picker).getByRole("option", { name: /Kochi/ })).toBeDisabled();
    fireEvent.change(picker, { target: { value: "1" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Move unit" }));
    expect(await within(dialog).findByText("That would go deeper than the levels this space has named. Name another level first.")).toBeVisible();
  });

  it("is read-only for a unit-scoped caller and offers the first unit when the tree is empty", async () => {
    list = { ...list, scoped: true };
    const { unmount } = renderIt();
    expect(await screen.findByText(/You see only your own unit/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Actions for North" })).toBeNull();
    expect(screen.queryByText("Level names")).toBeNull();
    unmount();
    list = { levels: ["Area", "Unit"], templates, units: [], limit: 5, used: 0, scoped: false };
    renderIt();
    expect(await screen.findByText("Add your first area")).toBeVisible();
    expect(screen.getByText("0 of 5 units used")).toBeVisible();
  });

  it("renders nothing while the switch is off", async () => {
    staffRequest.mockImplementation(() => Promise.reject(new StructuredApiError(404, { code: "feature_disabled", detail: "off" })));
    const { container } = renderIt();
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("fills level names from a template", async () => {
    renderIt();
    fireEvent.click(await screen.findByRole("button", { name: "State, district and chapter" }));
    expect(screen.getByLabelText("Level 3")).toHaveValue("Chapter");
    fireEvent.click(screen.getByRole("button", { name: "Save level names" }));
    await waitFor(() => expect(JSON.parse(String(calls("/member-unit-levels")[0][1].body))).toEqual({ levels: ["State", "District", "Chapter"] }));
  });
});
