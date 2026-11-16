import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { expectNoA11yViolations } from "../../../test/axe";
import { DiscountsPanel } from "./DiscountsPanel";
import type { PriceDiscount } from "./pricingApi";
import { PricingSettings } from "./PricingSettings";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const rule = (extra: Partial<PriceDiscount> = {}): PriceDiscount => ({
  id: 3, name: "Student rate", audience: "plan", plan: 11, plan_name: "Student", member: null, member_name: null,
  domains: ["loans"], components: [], percent_bps: 1500, amount_off: null, starts_at: null, ends_at: null, is_active: true,
  archived_at: null, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z", ...extra,
});
const archived = rule({ id: 4, name: "Old promo", audience: "all_members", plan: null, plan_name: null, percent_bps: null,
  amount_off: "5.00", archived_at: "2026-10-02T00:00:00Z", is_active: false });

function route(path: string, init?: RequestInit) {
  const method = init?.method ?? "GET";
  if (path.includes("/membership-plans")) return [{ id: 11, name: "Student", is_active: true }, { id: 12, name: "Pro", is_active: true }];
  if (path.startsWith("/admin/memberships?")) return { results: [{ id: 1, user: { id: 42, username: "asha", display_name: "Asha K" } }] };
  if (path.endsWith("/archive")) return { ...rule(), archived_at: "2026-10-31T00:00:00Z" };
  if (path.endsWith("/discounts?archived=1")) return [rule(), archived];
  if (path.endsWith("/discounts")) return method === "POST" ? rule({ id: 9 }) : [rule()];
  if (/\/discounts\/\d+$/.test(path)) return rule();
  throw new Error(`unexpected ${method} ${path}`);
}

function mount(canEdit = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>
    <DiscountsPanel makerspaceId={7} currency="usd" domains={["loans", "machines", "membership"]} membershipOn canEdit={canEdit} />
  </QueryClientProvider>);
}
const lastBody = (method: string) => JSON.parse(String(staffRequest.mock.calls.filter(([, init]) => init?.method === method).at(-1)![1].body));

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (path: string, init?: RequestInit) => route(path, init));
});

describe("DiscountsPanel", () => {
  it("lists active rules and archived ones on their own tab", async () => {
    const { container } = mount();
    expect(await screen.findByText("Student rate")).toBeVisible();
    expect(screen.getByText("15% off · Members on Student · Inventory")).toBeVisible();
    expect(screen.getByText(/Only the single best automatic discount applies/)).toBeVisible();
    await expectNoA11yViolations(container);
    fireEvent.click(screen.getByRole("tab", { name: "Archived" }));
    expect(await screen.findByText("Old promo")).toBeVisible();
    expect(screen.getByText("$5.00 off · All members · Inventory")).toBeVisible();
    expect(screen.queryByText("Student rate")).not.toBeInTheDocument();
    expect(screen.getByText(/Archived rules stop applying/)).toBeVisible();
  });

  it("archives after confirming", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Archive" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Archive discount" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/pricing/discounts/3/archive", { method: "POST", body: undefined }));
  });

  it("creates a plan discount from the plans list", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "New discount" }));
    fireEvent.click(screen.getByRole("button", { name: "Create discount" }));
    expect(await screen.findByText("Give the discount a name.")).toBeVisible();
    fireEvent.change(screen.getByRole("textbox", { name: /Name/ }), { target: { value: "Pro perk" } });
    fireEvent.click(screen.getByRole("radio", { name: "Members on a plan" }));
    await screen.findByRole("option", { name: "Pro" });
    fireEvent.change(screen.getByRole("combobox", { name: "Membership plan" }), { target: { value: "12" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Percent off/ }), { target: { value: "12.5" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Machines" }));
    fireEvent.click(screen.getByRole("button", { name: "Create discount" }));
    await waitFor(() => expect(lastBody("POST")).toMatchObject({ name: "Pro perk", audience: "plan", plan: 12, member: null,
      percent_bps: 1250, amount_off: null, domains: ["machines"], components: [], is_active: true }));
    expect(await screen.findByRole("button", { name: "New discount" })).toBeVisible();
  });

  it("targets one member by search with a fixed amount off", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "New discount" }));
    fireEvent.change(screen.getByRole("textbox", { name: /Name/ }), { target: { value: "Volunteer" } });
    fireEvent.click(screen.getByRole("radio", { name: "One member" }));
    const search = screen.getByRole("combobox", { name: "Member" });
    fireEvent.focus(search);
    fireEvent.change(search, { target: { value: "as" } });
    fireEvent.mouseDown(await screen.findByRole("option", { name: /Asha K/ }, { timeout: 2000 }));
    fireEvent.click(screen.getByRole("radio", { name: "Fixed amount off" }));
    fireEvent.change(screen.getByRole("textbox", { name: /Amount off/ }), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /Late fee per day/ }));
    fireEvent.click(screen.getByRole("button", { name: "Create discount" }));
    await waitFor(() => expect(lastBody("POST")).toMatchObject({ audience: "member", member: 42, plan: null,
      percent_bps: null, amount_off: "4", components: ["late_per_day"] }));
  });

  it("edits an existing rule and shows the server's refusal", async () => {
    staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
      if (init?.method === "PATCH") throw new StructuredApiError(400, { detail: "Those components are not in the chosen areas.", code: "discount_invalid" });
      return route(path, init);
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /Student rate/ }));
    expect(screen.getByRole("textbox", { name: /Percent off/ })).toHaveValue("15");
    fireEvent.click(screen.getByRole("button", { name: "Save discount" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The discount is not valid. Those components are not in the chosen areas.");
    expect(lastBody("PATCH")).toMatchObject({ plan: 11, percent_bps: 1500 });
  });

  it("is read-only for finance staff and hidden while charges.discounts is off", async () => {
    mount(false);
    expect(await screen.findByText("Student rate")).toBeVisible();
    expect(screen.queryByRole("button", { name: "New discount" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Archive" })).not.toBeInTheDocument();
  });

  it("is not mounted by the Pricing section without charges.discounts", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path.includes("/discounts")) throw new Error("should not load");
      if (path.endsWith("/currency")) return { default_currency: "usd" };
      if (path.endsWith("/rental-timing")) return { rental_timing: "at_checkout", editable: true, via: null, locked: false };
      return { domain: "loans", label: "Inventory", enabled: true, currency: "usd", mode: "free", stored: false, editable: true,
        via: null, locked: false, refusal: null, rental_timing: "at_checkout", rental_timing_editable: true, failed_job_charge: null,
        lines: [], lending: null };
    });
    render(<QueryClientProvider client={new QueryClient()}>
      {/* #184 G5 (0acf6df0): the Inventory card renders only where loan charges are tracked. */}
      <PricingSettings canManageMakerspace makerspace={{ id: 7, enabled_modules: ["request_workflow"],
        enabled_features: ["charges.pricing", "charges.enabled", "charges.loans"] }} />
    </QueryClientProvider>);
    expect(await screen.findByText(/Loans are free/)).toBeVisible();
    expect(screen.queryByText("Member discounts")).not.toBeInTheDocument();
  });
});
