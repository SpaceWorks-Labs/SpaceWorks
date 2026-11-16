import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConsumableProfileEditor } from "./ConsumableProfileEditor";
import { draftProblem, blankDraft, keyFromName, withUnit } from "./profileDraft";
import { poolUnitFor, productUnit } from "./profileUnits";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../../lib/api", async importOriginal => ({ ...(await importOriginal<object>()), staffRequest }));

const stock = { pools: [{ id: 5, label: "PLA spool", unit: "grams", remaining: "800" }, { id: 6, label: "Sheet stack", unit: "count", remaining: "40" }], products: [{ id: 3, name: "3 mm acrylic" }] };
const show = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ConsumableProfileEditor makerspaceId={1} typeId={9} /></QueryClientProvider>);
const mockApi = (rows: object[] = []) => staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
  if (path.includes("/consumable-stock")) return stock;
  if (init?.method === "POST") return { id: 2, ...JSON.parse(String(init.body)) };
  return rows;
});

describe("profile draft rules", () => {
  it("derives a server-valid key and blocks bad rows", () => {
    expect(keyFromName("3D Print Resin (ml)")).toBe("d_print_resin_ml");
    expect(keyFromName("Order ID")).toBe("order_id_x");
    expect(draftProblem(blankDraft(), true)).toMatch(/name/);
    expect(draftProblem({ ...blankDraft(), name: "X", key: "x", record_by: [] }, true)).toMatch(/records/);
    expect(draftProblem({ ...blankDraft(), name: "X", key: "x", unit: "g", product: 3 }, true)).toMatch(/product/);
    expect(draftProblem({ ...blankDraft(), name: "X", key: "x", unit_price: "-1" }, true)).toMatch(/price/);
    expect(draftProblem({ ...blankDraft(), name: "X", key: "x" }, true)).toBe("");
  });
  it("maps units to the pool family and drops a mismatched link", () => {
    expect(poolUnitFor("kg")).toBe("grams");
    expect(poolUnitFor("l")).toBe("milliliters");
    expect(poolUnitFor("min")).toBeNull();
    expect(productUnit("sheet")).toBe(true);
    expect(productUnit("g")).toBe(false);
    const linked = { ...blankDraft(), consumable_pool: 5 };
    expect(withUnit(linked, "sheet", () => "grams").consumable_pool).toBeNull();
    expect(withUnit(linked, "kg", () => "grams").consumable_pool).toBe(5);
  });
});

describe("ConsumableProfileEditor", () => {
  beforeEach(() => { staffRequest.mockReset(); });

  it("filters stock by unit and sends the row with the required flag", async () => {
    mockApi();
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Add a custom consumable" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Acrylic" } });
    expect(screen.getByLabelText("Key")).toHaveValue("acrylic");
    fireEvent.change(screen.getByLabelText("Unit"), { target: { value: "g" } });
    await waitFor(() => expect(screen.getByRole("option", { name: /PLA spool/ })).toBeInTheDocument());
    expect(screen.queryByRole("option", { name: /Sheet stack/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Linked product")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Unit"), { target: { value: "sheet" } });
    await waitFor(() => expect(screen.getByRole("option", { name: /Sheet stack/ })).toBeInTheDocument());
    expect(screen.queryByRole("option", { name: /PLA spool/ })).not.toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "3 mm acrylic" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: /Required/ }));
    fireEvent.click(screen.getByRole("button", { name: "Add consumable" }));
    await waitFor(() => expect(staffRequest.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    const body = JSON.parse(staffRequest.mock.calls.find(([, init]) => init?.method === "POST")![1].body);
    expect(body).toMatchObject({ key: "acrylic", name: "Acrylic", unit: "sheet", required: true, record_by: ["staff"], consumable_pool: null });
  });

  it("refuses a row nobody records and locks the unit of a used row", async () => {
    mockApi([{ id: 1, machine_type: 9, key: "pla", name: "PLA", kind: "material", unit: "g", attributes: {}, required: false, estimate_by: "none", record_by: ["staff"],
      unit_price: null, consumable_pool: null, product: null, position: 0, is_active: true, in_use: true }]);
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
    expect(screen.getByLabelText(/^Unit/)).toBeDisabled();
    expect(screen.getByLabelText("Key")).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: "Staff" }));
    expect(screen.getByRole("button", { name: "Save consumable" })).toBeDisabled();
    expect(screen.getByText("Choose who records the amount used.")).toBeVisible();
  });
});
