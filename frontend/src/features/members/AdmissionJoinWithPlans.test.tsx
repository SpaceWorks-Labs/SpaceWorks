import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdmissionJoinWithPlans } from "./AdmissionJoinWithPlans";
import type { PublicAdmission } from "./membershipAdmissionApi";
import type { PublicUnits } from "./joinUnitsApi";

const { tenantPublicRequest } = vi.hoisted(() => ({ tenantPublicRequest: vi.fn() }));
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, tenantPublicRequest };
});

const settings: PublicAdmission = { join_mode: "open", vouches_required: 0, payment_timing: "after_activation",
  application_schema: [], default_plan: null, joining_fee: "0.00" };
const plan = (id: number, name: string) => ({ id, slug: name.toLowerCase(), name, description: "", plan_type: "rolling", interval: "yearly",
  custom_days: null, fixed_end_date: null, amount: "0.00", renewal_price: "0.00", currency: "inr", joining_fee: null,
  join_mode: "open" as const, sort_order: id });
const units = [{ code: "NORTH", name: "North", level: 0, level_name: "District", parent_code: null },
  { code: "KOCHI", name: "Kochi", level: 1, level_name: "Chapter", parent_code: "NORTH" }];
let unitsOff = false;

beforeEach(() => {
  unitsOff = false;
  tenantPublicRequest.mockReset();
  tenantPublicRequest.mockImplementation((_slug: string, path: string) => {
    if (path.endsWith("/membership-plans")) return Promise.resolve([plan(1, "Everywhere"), plan(2, "Kochi only")]);
    if (path.includes("/member-units")) {
      if (unitsOff) return Promise.reject(new Error("Not found"));
      const code = new URLSearchParams(path.split("?")[1] ?? "").get("code") ?? "";
      const selected = units.find(unit => unit.code === code) ?? null;
      const body: PublicUnits = { levels: ["District", "Chapter"], units, selected,
        plan_ids: selected ? (selected.code === "KOCHI" ? [1, 2] : [1]) : null };
      return Promise.resolve(body);
    }
    return Promise.reject(new Error("unexpected"));
  });
});

const renderJoin = (url: string, onJoin = vi.fn()) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter initialEntries={[url]}><AdmissionJoinWithPlans slug="ws" settings={settings} signedIn pending={false} onJoin={onJoin} onSignIn={vi.fn()} /></MemoryRouter>
</QueryClientProvider>);

describe("join page unit picker (parity O-F1)", () => {
  it("preselects ?unit=CODE, shows only that unit's plans and sends the unit code", async () => {
    const onJoin = vi.fn();
    renderJoin("/m/ws/join?unit=kochi", onJoin);
    expect(await screen.findByText("You are joining Kochi (Chapter).")).toBeVisible();
    expect(await screen.findByRole("radio", { name: /Kochi only/ })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Join instantly" }));
    expect(onJoin).toHaveBeenCalledWith({}, { unit_code: "KOCHI" });
  });

  it("narrows the plans when the applicant picks a unit", async () => {
    renderJoin("/m/ws/join");
    const picker = await screen.findByRole("combobox", { name: "Your District" });
    expect(await screen.findByRole("radio", { name: /Kochi only/ })).toBeVisible();
    fireEvent.change(picker, { target: { value: "NORTH" } });
    await waitFor(() => expect(screen.queryByRole("radio", { name: /Kochi only/ })).toBeNull());
    expect(screen.getByText("Showing the plans offered in North.")).toBeVisible();
  });

  it("says when a unit link is no longer valid", async () => {
    renderJoin("/m/ws/join?unit=GONE");
    expect(await screen.findByText("That unit link is no longer valid. Choose your unit below.")).toBeVisible();
  });

  it("shows no picker when the space does not use units", async () => {
    unitsOff = true;
    renderJoin("/m/ws/join?unit=KOCHI");
    expect(await screen.findByRole("radio", { name: /Kochi only/ })).toBeVisible();
    expect(screen.queryByRole("combobox")).toBeNull();
  });
});
