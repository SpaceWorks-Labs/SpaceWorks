import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { DamageChargeDialog, DamageChargeStep, needsDamageCharges } from "./DamageChargeStep";
import { LoanChargesPanel } from "./LoanChargesPanel";
import { WAIVE_SUMMARY, WaiveFeesDialog, waiverPreview } from "./WaiveFeesDialog";
import type { LoanAccountabilityRow, LoanCharges } from "./loanChargesApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

function renderWithClient(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

const damaged: LoanAccountabilityRow = { id: 31, issue_type: "damaged", quantity: 1, item_label: "Soldering iron",
  has_return_photo: true, suggested_amount: "25.00", suggested_source: "unit_cost", charge: null, no_charge_decided: false };
const lost: LoanAccountabilityRow = { id: 32, issue_type: "missing", quantity: 2, item_label: "Multimeter",
  has_return_photo: false, suggested_amount: "40.00", suggested_source: "product", charge: null, no_charge_decided: false };
const charge = (id: number, subject_type: string, label: string, amount: string, status: string) =>
  ({ id, subject_type, subject_id: 9, label, amount, currency: "usd", status, created_at: "2026-10-20T10:00:00Z" });
const charges = [charge(1, "loan_deposit", "Loan deposit", "50.00", "paid_offline"),
  charge(2, "loan_late_fee", "Late return fee", "6.00", "pending"), charge(3, "loan_rental", "Rental", "10.00", "paid_online")];
const waiver = { id: 5, request: 9, components: ["late"], covered: ["late"], reason: "Bus strike", revokes: null,
  revoked: false, created_by: 2, created_by_name: "Dana Desk", created_at: "2026-10-26T09:30:00Z" };

function payload(patch: Partial<LoanCharges> = {}): LoanCharges {
  return { request_id: 9, currency: "usd", pricing_enabled: true, charges_enabled: true, waivers_enabled: true, can_waive: true, charges,
    waivers: [waiver], accountability: [damaged, lost], ...patch };
}

function serve(data: LoanCharges, post: (path: string, init: RequestInit) => unknown = () => ({ charge: null, free_reason: "no_charge" })) {
  staffRequest.mockImplementation((path: string, init?: RequestInit) =>
    init?.method === "POST" ? Promise.resolve(post(path, init)) : Promise.resolve(data));
}
const posted = (suffix: string) => staffRequest.mock.calls.find(([path, init]) => String(path).endsWith(suffix) && init?.method === "POST");

beforeEach(() => { staffRequest.mockReset(); });

describe("LoanChargesPanel", () => {
  it("lists charges with status, damage rows and the waiver history", async () => {
    serve(payload());
    renderWithClient(<LoanChargesPanel loan={{ id: 9, status: "returned", makerspace_id: 7 }} />);
    expect(await screen.findByText("Late return fee")).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/requests/9/charges");
    expect(screen.getByText("Paid in person")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Set charge for Soldering iron · 1 damaged" })).toBeInTheDocument();
    const history = screen.getByRole("region", { name: "Fee waivers" });
    expect(within(history).getByText(/Waiver #5 · Late fee/)).toBeInTheDocument();
    expect(within(history).getByText("Bus strike")).toBeInTheDocument();
    expect(within(history).getByText(/Dana Desk/)).toBeInTheDocument();
  });

  it("revoking a waiver needs a reason", async () => {
    serve(payload(), () => ({ ...waiver, id: 6, revokes: 5 }));
    renderWithClient(<LoanChargesPanel loan={{ id: 9, status: "returned", makerspace_id: 7 }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Revoke waiver #5" }));
    const dialog = screen.getByRole("dialog", { name: "Revoke fee waiver" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Revoke waiver" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent(/Give a reason/);
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "Charged by mistake" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Revoke waiver" }));
    await waitFor(() => expect(posted("/fee-waivers/5/revoke")?.[1].body).toBe(JSON.stringify({ reason: "Charged by mistake" })));
  });

  it("hides the waive action, history and damage rows when the space switches them off", async () => {
    serve(payload({ waivers_enabled: false, can_waive: false, pricing_enabled: false }));
    renderWithClient(<LoanChargesPanel loan={{ id: 9, status: "returned", makerspace_id: 7 }} />);
    expect(await screen.findByText("Rental")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Waive fees" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Fee waivers" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Soldering iron/)).not.toBeInTheDocument();
  });

  it("stays out of the way before a loan can owe anything, or when the viewer may not read it", async () => {
    const { container } = renderWithClient(<LoanChargesPanel loan={{ id: 9, status: "pending_approval", makerspace_id: 7 }} />);
    expect(container).toBeEmptyDOMElement();
    expect(staffRequest).not.toHaveBeenCalled();
    staffRequest.mockImplementation(() => Promise.reject(new StructuredApiError(404, { detail: "Not found." })));
    const second = renderWithClient(<LoanChargesPanel loan={{ id: 9, status: "issued", makerspace_id: 7 }} />);
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    await waitFor(() => expect(second.container).toBeEmptyDOMElement());
  });
});

describe("WaiveFeesDialog", () => {
  it("waives every loan fee by default, with the summary and the outcome", async () => {
    serve(payload(), () => ({ waiver, waived_payment_ids: [2], refund_case_ids: [40] }));
    renderWithClient(<WaiveFeesDialog makerspaceId={7} requestId={9} charges={charges} onClose={() => {}} />);
    expect(screen.getByText(WAIVE_SUMMARY)).toBeInTheDocument();
    expect(screen.getByText(/1 pending charge to waive, 1 paid charge to send to a refund case/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Waive fees" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/Give a reason/);
    fireEvent.change(screen.getByRole("textbox", { name: /Reason/ }), { target: { value: "Member hardship" } });
    fireEvent.click(screen.getByRole("button", { name: "Waive fees" }));
    expect(await screen.findByText("1 pending charge waived.")).toBeInTheDocument();
    expect(screen.getByText(/1 refund case opened/)).toBeInTheDocument();
    expect(JSON.parse(posted("/fee-waivers")![1].body)).toEqual({ components: [], reason: "Member hardship" });
  });

  it("sends only the chosen fees and explains a fee that is already waived", async () => {
    staffRequest.mockImplementation(() => Promise.reject(new StructuredApiError(409, { detail: "Exists", code: "waiver_exists" })));
    renderWithClient(<WaiveFeesDialog makerspaceId={7} requestId={9} charges={charges} onClose={() => {}} />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Rental" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Damage" }));
    fireEvent.change(screen.getByRole("textbox", { name: /Reason/ }), { target: { value: "Goodwill" } });
    fireEvent.click(screen.getByRole("button", { name: "Waive fees" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/already waived/);
    expect(JSON.parse(staffRequest.mock.calls[0][1].body)).toEqual({ components: ["late", "lost"], reason: "Goodwill" });
  });

  it("previews what the chosen fees touch, never the deposit", () => {
    expect(waiverPreview(charges, ["rental", "late", "damage", "lost"])).toEqual({ pending: 1, paid: 1 });
    expect(waiverPreview(charges, ["damage"])).toEqual({ pending: 0, paid: 0 });
  });
});

describe("Damage and lost charge step", () => {
  it("prefills the suggestion, saves a charge and offers No charge", async () => {
    serve(payload(), (path) => path.includes("/31/") ? { charge: { ...charges[1], id: 8, subject_type: "loan_damage", amount: "25.00" }, free_reason: null }
      : { charge: null, free_reason: "no_charge" });
    renderWithClient(<DamageChargeStep makerspaceId={7} requestId={9} />);
    const iron = await screen.findByRole("form", { name: "Soldering iron · 1 damaged" });
    expect(within(iron).getByRole("textbox", { name: /Amount/ })).toHaveValue("25.00");
    expect(within(iron).getByText("Suggested from the item's unit cost.")).toBeInTheDocument();
    fireEvent.click(within(iron).getByRole("button", { name: /Save charge of/ }));
    expect(await screen.findByText(/Charged \$25\.00/)).toBeInTheDocument();
    expect(JSON.parse(posted("/accountability/31/charge")![1].body)).toEqual({ amount: "25.00" });
  });

  it("disables the amount without a return photo and can be left for later", async () => {
    serve(payload());
    renderWithClient(<DamageChargeStep makerspaceId={7} requestId={9} />);
    const meter = await screen.findByRole("form", { name: "Multimeter · 2 lost" });
    expect(within(meter).getByRole("textbox", { name: /Amount/ })).toBeDisabled();
    expect(within(meter).getByText(/No return photo recorded this item/)).toBeInTheDocument();
    fireEvent.change(within(meter).getByRole("textbox", { name: /Note/ }), { target: { value: "Lost on the bus" } });
    fireEvent.click(within(meter).getByRole("button", { name: "Save: no charge" }));
    await waitFor(() => expect(JSON.parse(posted("/accountability/32/charge")![1].body)).toEqual({ amount: "0", note: "Lost on the bus" }));
    fireEvent.click(screen.getByRole("button", { name: "Decide later" }));
    expect(screen.getByText(/Charges left for later/)).toBeInTheDocument();
  });

  it("only follows a return that recorded damage or loss with price lists on", async () => {
    // #184 G5 (0acf6df0): the step also needs loan charges tracked (charges.enabled + charges.loans).
    const space = { enabled_features: ["charges.enabled", "charges.loans", "charges.pricing"], enabled_modules: ["request_workflow"] };
    expect(needsDamageCharges(space, [{ damaged: 0, missing: 1 }])).toBe(true);
    expect(needsDamageCharges(space, [{ damaged: 0, missing: 0 }])).toBe(false);
    expect(needsDamageCharges({ enabled_features: [] }, [{ damaged: 2, missing: 0 }])).toBe(false);
    expect(needsDamageCharges({ enabled_features: ["charges.pricing"], enabled_modules: ["request_workflow"] }, [{ damaged: 2, missing: 0 }])).toBe(false);
    serve(payload({ accountability: [{ ...damaged, charge: charges[1] }] }));
    const onClose = vi.fn();
    renderWithClient(<DamageChargeDialog makerspaceId={7} requestId={9} onClose={onClose} />);
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("No charge decisions", () => {
  it("shows a decided No charge in the panel, still chargeable, and leaves it out of the return step", async () => {
    serve(payload({ accountability: [{ ...damaged, no_charge_decided: true }, lost] }));
    renderWithClient(<LoanChargesPanel loan={{ id: 9, status: "returned", makerspace_id: 7 }} />);
    expect(await screen.findByText("No charge (decided)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Set charge for Soldering iron · 1 damaged" })).toBeInTheDocument();
    renderWithClient(<DamageChargeStep makerspaceId={7} requestId={9} />);
    expect(await screen.findByRole("form", { name: "Multimeter · 2 lost" })).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Soldering iron · 1 damaged" })).not.toBeInTheDocument();
  });
});

// Decision 242(a), audit M4: issue/return holders record cash received on a loan charge.
describe("LoanChargesPanel settle (decision 242 a)", () => {
  it("offers Mark offline on a pending charge to whoever takes returns, and posts the receipt", async () => {
    const { StaffListContext } = await import("../StaffListContext");
    serve(payload(), () => ({ ...charges[1], status: "paid_offline" }));
    renderWithClient(<StaffListContext.Provider value={{ ownerName: "x", canShare: false, actions: ["return_request"], makerspace: { id: 7 } }}>
      <LoanChargesPanel loan={{ id: 9, status: "returned", makerspace_id: 7 }} /></StaffListContext.Provider>);
    const late = (await screen.findByText("Late return fee")).closest("li")!;
    fireEvent.click(within(late).getByRole("button", { name: "Mark offline" }));
    fireEvent.click(screen.getByRole("button", { name: "Save receipt" }));
    await waitFor(() => expect(posted("/payments/2/mark-offline")).toBeTruthy());
    // Paid charges carry no settle control.
    expect(within((screen.getByText("Loan deposit")).closest("li")!).queryByRole("button", { name: "Mark offline" })).toBeNull();
  });

  it("shows no settle control to someone without loan-charge authority", async () => {
    serve(payload());
    renderWithClient(<LoanChargesPanel loan={{ id: 9, status: "returned", makerspace_id: 7 }} />);
    await screen.findByText("Late return fee");
    expect(screen.queryByRole("button", { name: "Mark offline" })).toBeNull();
  });
});
