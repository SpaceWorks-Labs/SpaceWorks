import { describe, expect, it, vi, afterEach } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { CancelObligation } from "./CancelObligation";
import { PayeeReview } from "./PayeeReview";
import { PayoutHolds } from "./PayoutHolds";
import { PayoutDashboard } from "./PayoutDashboard";
import { payout, scope } from "./testData";
import { expectNoA11yViolations } from "../../../test/axe";

const { mutate, dashboard } = vi.hoisted(() => ({ mutate: vi.fn(), dashboard: vi.fn() }));
vi.mock("./api", () => ({ usePayoutCommand: () => ({ mutate, isPending: false, isSuccess: false, error: null }),
  usePayoutDashboard: () => dashboard() }));
afterEach(() => { vi.clearAllMocks(); });
describe("server-driven finance actions", () => {
  it("has no mutating controls without action flags", () => {
    const row = { ...payout, allowed_actions: undefined };
    render(<><CancelObligation scope={scope} payout={row} /><PayeeReview scope={scope} payout={row} /><PayoutHolds scope={scope} payout={row} /></>);
    expect(screen.queryByRole("button")).toBeNull();
  });
  it("confirms cancellation and sends detached null pool plus both versions", async () => {
    const { container } = render(<CancelObligation scope={scope} payout={payout} />);
    fireEvent.change(screen.getByLabelText("Reason code"), { target: { value: "duplicate_liability" } });
    fireEvent.change(screen.getByLabelText("Finance explanation"), { target: { value: "Reviewed duplicate obligation" } });
    fireEvent.click(screen.getByLabelText("I confirm this unpaid obligation should be cancelled."));
    fireEvent.click(screen.getByRole("button", { name: "Cancel unpaid obligation" }));
    expect(mutate).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeVisible();
    await expectNoA11yViolations(container);
    fireEvent.click(screen.getByRole("button", { name: "Confirm cancellation" }));
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ expected_version: 3, expected_revision_sequence: 1,
      expected_pool_version: null, reason_code: "duplicate_liability" }), expect.anything());
  });
  it.each([{ ...payout, coordination_state: "attached" as const }, { ...payout, effective_paid_minor: 1 }])("refuses cancellation when unpaid/current-pool preconditions are missing", row => {
    render(<CancelObligation scope={scope} payout={row} />);
    expect(screen.getByRole("button", { name: "Cancel unpaid obligation" })).toBeDisabled();
  });
  it("requires inspected confirmation and sends exact payee revision for verification", () => {
    render(<PayeeReview scope={scope} payout={payout} />);
    expect(screen.getByRole("button", { name: "Verify inspected routing" })).toBeDisabled();
    fireEvent.click(screen.getByLabelText("I inspected this payee revision and confirmed its routing."));
    fireEvent.click(screen.getByRole("button", { name: "Verify inspected routing" }));
    expect(mutate).toHaveBeenCalledWith({ expected_version: 3, payee_revision_id: "payee", expected_payee_version: 1 });
    fireEvent.change(screen.getByLabelText("Payee review reason code"), { target: { value: "routing_mismatch" } });
    fireEvent.change(screen.getByLabelText("Correction explanation"), { target: { value: "Please review the receiving account" } });
    fireEvent.click(screen.getByRole("button", { name: "Request owner correction" }));
    expect(mutate).toHaveBeenLastCalledWith(expect.objectContaining({ reason_code: "routing_mismatch", note: "Please review the receiving account" }));
  });
  it("binds acknowledgement and hold release to current eligibility", async () => {
    const { container } = render(<PayoutHolds scope={scope} payout={{ ...payout, holds: [{ id: "hold", kind: "eligibility",
      reason_code: "attendance_changed", hold_until: null, allowed_actions: ["release_hold"] }] }} />);
    const ack = within(screen.getByRole("form", { name: "Acknowledge eligibility correction" }));
    fireEvent.change(ack.getByLabelText("Acknowledgement reason code"), { target: { value: "evidence_reviewed" } });
    fireEvent.click(ack.getByLabelText("I reviewed the corrected evidence."));
    fireEvent.click(ack.getByRole("button", { name: "Acknowledge eligibility" }));
    expect(mutate).toHaveBeenCalledWith({ expected_version: 3, eligibility_revision: 2, reason_code: "evidence_reviewed" });
    const release = within(screen.getByRole("form", { name: "Release hold hold" }));
    fireEvent.change(release.getByLabelText("Hold reason code"), { target: { value: "fresh_venue_proof" } });
    fireEvent.click(release.getByLabelText("I confirm this finance release."));
    fireEvent.click(release.getByRole("button", { name: "Release hold" }));
    expect(mutate).toHaveBeenLastCalledWith(expect.objectContaining({ hold_id: "hold", kind: "eligibility", eligibility_revision: 2 }));
    await expectNoA11yViolations(container);
  });
  it("keeps currencies separate and unavailable pool data distinct from zero", async () => {
    dashboard.mockReturnValue({ isPending: false, error: null, data: { pool_provider_available: false, currencies: [
      { currency: "INR", pool_minor: null, awarded_minor: null, claimed_minor: null, approved_minor: 100, paid_minor: 0,
        awaiting_payout_minor: 100, awaiting_payout_count: 1, claim_ageing: null },
      { currency: "JPY", pool_minor: 2000, awarded_minor: 1000, claimed_minor: 500, approved_minor: 500, paid_minor: 200,
        awaiting_payout_minor: 300, awaiting_payout_count: 2, claim_ageing: [{ label: "0–7 days", count: 2, amount_minor: 500 }] },
    ] } });
    const { container } = render(<PayoutDashboard scope={scope} />);
    expect(screen.getByRole("heading", { name: "INR" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "JPY" })).toBeVisible();
    expect(screen.getByText("0–7 days")).toBeVisible();
    expect(screen.getByText(/Core payout balances remain available/)).toBeVisible();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    await expectNoA11yViolations(container);
  });
});
