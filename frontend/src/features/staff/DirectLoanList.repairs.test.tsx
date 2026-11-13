/** Inventory journey (0.12.0): a direct handout returned damaged can be sent to repairs from its row. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../lib/api")>(), staffRequest }));

import { DirectLoanList, type DirectLoan } from "./DirectLoanList";
import { StaffListContext } from "./StaffListContext";

const loan = (status: string): DirectLoan => ({ id: 5, request_id: 50, public_token: "tok", status, target_label: "Drill",
  due_at: null, issued_by: null, items: [{ product_name: "Drill", quantity: 1 }] });

function show(rows: DirectLoan[], features: string[]) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <StaffListContext.Provider value={{ ownerName: "sm", canShare: false, makerspace: { id: 3, enabled_features: features } }}>
      <DirectLoanList loans={rows} onReturn={vi.fn()} makerspaceId={3} />
    </StaffListContext.Provider></QueryClientProvider>);
}
const openMenu = () => fireEvent.click(screen.getByRole("button", { name: "More actions for handout 5" }));

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation((path: string) => path.endsWith("/charges") || path.includes("charges")
    ? Promise.reject(new Error("not used")) : Promise.resolve({ request_id: 50, lines: [{ accountability_id: 8, product_name: "Drill",
      quantity: 1, asset_tag: "", remark: "Chuck cracked", evidence_id: 2, issue: null }] }));
});

it("opens the damaged lines of a returned handout and offers Send to repairs", async () => {
  show([loan("returned")], ["loans.enabled", "inventory.repairs"]);
  openMenu();
  fireEvent.click(screen.getByRole("menuitem", { name: "Repairs" }));
  expect(await screen.findByRole("button", { name: /Send Drill · 1 damaged to repairs/ })).toBeVisible();
  expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/requests/50/repairs");
});

it("says so when nothing on the handout came back damaged", async () => {
  staffRequest.mockResolvedValue({ request_id: 50, lines: [] });
  show([loan("returned")], ["loans.enabled", "inventory.repairs"]);
  openMenu();
  fireEvent.click(screen.getByRole("menuitem", { name: "Repairs" }));
  expect(await screen.findByText("Nothing on this loan came back damaged.")).toBeVisible();
});

it("offers no Repairs action while the handout is still out", () => {
  show([{ ...loan("checked_out"), issue_evidence_id: 1 }], ["loans.enabled", "inventory.repairs"]);
  openMenu();
  expect(screen.queryByRole("menuitem", { name: "Repairs" })).toBeNull();
});

it("offers no Repairs action when inventory repairs are switched off", () => {
  show([{ ...loan("returned"), return_evidence_id: 2 }], []);
  openMenu();
  expect(screen.queryByRole("menuitem", { name: "Repairs" })).toBeNull();
});
