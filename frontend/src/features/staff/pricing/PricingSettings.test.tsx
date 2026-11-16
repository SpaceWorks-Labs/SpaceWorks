import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { expectNoA11yViolations } from "../../../test/axe";
import { hubEntries, searchHub } from "../settingsHubCatalog";
import type { PricingDefault } from "./pricingApi";
import { PricingSettings } from "./PricingSettings";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const line = (component: string, extra: Partial<PricingDefault["lines"][number]> = {}) => ({
  component, label: component, unit: "item", has_cap: false, has_grace: false, has_increment: false, has_minimum: false,
  discountable: true, staff_set: false, prefill_only: false, read_only: false, amount: "0.00", cap: null, grace_units: 0,
  billing_increment: 0, minimum: 0, source: "none", ...extra,
});
const loans = (extra: Partial<PricingDefault> = {}): PricingDefault => ({
  domain: "loans", label: "Inventory", enabled: true, currency: "usd", mode: "paid", stored: true, editable: true,
  via: "space_manager", locked: false, refusal: null, rental_timing: "at_checkout", rental_timing_editable: true,
  failed_job_charge: null, lending: { deposit_mode: "none", deposit_amount: "0.00", deposit_blocks_issue: false,
    late_per_day: "0.00", late_cap: "0.00", grace_days: 0 },
  lines: [line("rental_per_loan", { label: "Rental per loan", amount: "2.00" }),
    line("rental_per_day", { label: "Rental per day", unit: "item_day", has_cap: true, amount: "5.00" }),
    line("damage", { label: "Damage", staff_set: true, discountable: false })], ...extra,
});
const machines: PricingDefault = { ...loans(), domain: "machines", label: "Machines", lending: null, rental_timing: null,
  failed_job_charge: "none", lines: [line("time", { label: "Machine time per hour", unit: "hour", has_increment: true, has_minimum: true })] };
const membership: PricingDefault = { ...loans(), domain: "membership", label: "Membership", lending: null, editable: false,
  refusal: "setting_not_delegated", lines: [line("dues", { label: "Membership dues", unit: "term", read_only: true, amount: "30.00" })] };

let timing = { rental_timing: "at_checkout", editable: true, via: "space_manager", locked: false };
let card = loans();
const impact = { domain: "loans", currency: "usd", items_checked: 4, changed: 1, truncated: false,
  changes: [{ target_type: "inventory_product", target_id: 9, label: "Drill", component: "rental_per_day", before: "5.00", after: "6.00", source: "default" }] };

function route(path: string, init?: RequestInit) {
  const method = init?.method ?? "GET";
  if (path.endsWith("/pricing/currency")) return method === "PUT" ? JSON.parse(String(init!.body)) : { default_currency: "usd" };
  if (path.endsWith("/rental-timing")) {
    if (method === "PUT") timing = { ...timing, ...JSON.parse(String(init!.body)) };
    return timing;
  }
  if (path.endsWith("/impact")) return impact;
  if (path.endsWith("/pricing/machines")) return machines;
  if (path.endsWith("/pricing/membership")) return membership;
  if (path.endsWith("/pricing/loans")) return method === "PUT" ? card : card;
  throw new Error(`unexpected ${method} ${path}`);
}

function mount(space: { enabled_modules?: string[]; enabled_features?: string[] } = {}, canManage = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>
    {/* #184 G5 (0acf6df0): each area's rate card shows only where that area's charges are tracked. */}
    <PricingSettings canManageMakerspace={canManage} makerspace={{ id: 7, enabled_modules: ["request_workflow", "machines", "membership"],
      enabled_features: ["charges.pricing", "charges.enabled", "charges.loans", "charges.machines", "charges.membership"], ...space }} />
  </QueryClientProvider>);
}

beforeEach(() => {
  timing = { rental_timing: "at_checkout", editable: true, via: "space_manager", locked: false };
  card = loans();
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (path: string, init?: RequestInit) => route(path, init));
});

describe("PricingSettings", () => {
  it("renders nothing while charges.pricing is off", () => {
    const { container } = mount({ enabled_features: [] });
    expect(container).toBeEmptyDOMElement();
    expect(staffRequest).not.toHaveBeenCalled();
  });

  it("shows one tab per installed area, the currency and a live worked example", async () => {
    const { container } = mount();
    const tabs = screen.getByRole("tablist", { name: "Pricing areas" });
    expect(within(tabs).getAllByRole("tab").map(tab => tab.textContent)).toEqual(["Inventory", "Machines", "Membership"]);
    expect(await screen.findByRole("textbox", { name: /Currency for new charges/ })).toHaveValue("USD");
    expect(await screen.findByText("A 3-day loan of 1 item costs $17.00 in rental.")).toBeVisible();
    expect(screen.getByText("per item per day")).toBeVisible();
    expect(screen.getByText(/Suggested default; staff set the actual charge at return/)).toBeVisible();
    fireEvent.change(screen.getByRole("textbox", { name: /Rental per day cap/ }), { target: { value: "8" } });
    expect(screen.getByText("A 3-day loan of 1 item costs $10.00 in rental.")).toBeVisible();
    expect(await screen.findByRole("radio", { name: /At return, for the actual days/ })).toBeEnabled();
    await expectNoA11yViolations(container);
  });

  it("previews the impact, then saves on confirm", async () => {
    mount();
    fireEvent.change(await screen.findByRole("textbox", { name: /Rental per day amount/ }), { target: { value: "6.00" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    const dialog = await screen.findByRole("dialog", { name: "Save inventory prices?" });
    expect(within(dialog).getByText("Drill")).toBeVisible();
    expect(within(dialog).getByText("$5.00 to $6.00")).toBeVisible();
    const body = JSON.parse(String(staffRequest.mock.calls.find(([path]) => String(path).endsWith("/impact"))![1].body));
    expect(body.lines).toContainEqual({ component: "rental_per_day", amount: "6.00", cap: null });
    expect(body.lending).toEqual({ deposit_mode: "none", deposit_amount: "0.00", deposit_blocks_issue: false,
      late_per_day: "0.00", late_cap: "0.00", grace_days: 0 });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save prices" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/pricing/loans",
      expect.objectContaining({ method: "PUT", body: JSON.stringify(body) })));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("names a refused save and an empty impact", async () => {
    staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
      if (init?.method === "PUT" && path.endsWith("/pricing/loans")) {
        throw new StructuredApiError(403, { detail: "Locked.", code: "setting_locked" });
      }
      if (path.endsWith("/impact")) return { ...impact, changed: 0, changes: [] };
      return route(path, init);
    });
    mount();
    fireEvent.change(await screen.findByRole("textbox", { name: /Rental per loan amount/ }), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("No item changes price.")).toBeVisible();
    fireEvent.click(within(dialog).getByRole("button", { name: "Save prices" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("The Space Manager has locked these prices");
  });

  it("lets an Inventory Manager change only the rental timing", async () => {
    card = loans({ editable: false, refusal: "setting_not_delegated", via: null });
    mount({}, false);
    expect(await screen.findByText(/You can see these prices but not change them/)).toBeVisible();
    expect(screen.getByRole("textbox", { name: /Rental per loan amount/ })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /Currency for new charges/ })).toBeDisabled();
    fireEvent.click(await screen.findByRole("radio", { name: /At return, for the actual days/ }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/pricing/loans/rental-timing",
      { method: "PUT", body: JSON.stringify({ rental_timing: "at_return" }) }));
    expect(await screen.findByText("Rental timing saved.")).toBeVisible();
  });

  it("shows machines' failed-job rule as text and membership as read-only", async () => {
    mount();
    fireEvent.click(screen.getByRole("tab", { name: "Machines" }));
    expect(await screen.findByText("Failed jobs: free by default.")).toBeVisible();
    expect(screen.getByRole("textbox", { name: /billing increment/ })).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: "Membership" }));
    expect(await screen.findByText("Set on each membership plan; plans own their prices.")).toBeVisible();
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /Membership dues/ })).not.toBeInTheDocument();
  });

  it("hides the currency control on 404", async () => {
    staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.endsWith("/pricing/currency")) throw new StructuredApiError(404, { detail: "Not found." });
      return route(path, init);
    });
    mount();
    await screen.findByText(/A 3-day loan/);
    expect(screen.queryByRole("textbox", { name: /Currency for new charges/ })).not.toBeInTheDocument();
  });

  it("is findable from the settings hub", () => {
    expect(searchHub(hubEntries(["pricing", "money"], []), "discount").map(entry => entry.id)).toEqual(["pricing"]);
    expect(searchHub(hubEntries([], ["stocktake"]), "stocktake").map(entry => entry.id)).toEqual(["tab:stocktake"]);
  });
});
