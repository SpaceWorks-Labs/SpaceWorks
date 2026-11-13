import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { PayoutRecording } from "./PayoutRecording";
import { entry, payout, scope } from "./testData";
const mutate = vi.hoisted(() => vi.fn());
vi.mock("./api", () => ({ usePayoutCommand: () => ({ mutate, isPending: false, isSuccess: false, error: null }) }));
afterEach(() => { mutate.mockReset(); });
const confirm = () => fireEvent.click(screen.getByLabelText("I confirm this records a payment or corrects its history."));
function fill() {
  fireEvent.change(screen.getByLabelText("Amount (INR)"), { target: { value: "1.00" } });
  fireEvent.change(screen.getByLabelText("Payment reference"), { target: { value: "CASH-2" } });
  fireEvent.change(screen.getByLabelText("Paid at (UTC)"), { target: { value: "2026-01-18T10:00" } });
}
describe("record-only payout form", () => {
  it("permits a zero void correction and preserves historical nullable payee", () => {
    render(<PayoutRecording scope={scope} payout={payout} amends={{ ...entry, payee_revision_id: null }} />);
    fireEvent.change(screen.getByLabelText("Correction reason code"), { target: { value: "duplicate_record" } });
    fireEvent.click(screen.getByLabelText("Void an erroneous record (does not return money)")); confirm();
    fireEvent.click(screen.getByRole("button", { name: "Append correction" }));
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ amount_minor: 0, is_void: true, payee_revision: null,
      paid_at: "2026-01-18T10:00:00Z", reason_code: "duplicate_record" }));
    expect(screen.queryByRole("button", { name: /^pay$/i })).toBeNull();
  });
  it("requires human confirmation, bounds the balance and rejects future time", () => {
    render(<PayoutRecording scope={scope} payout={payout} />); fill();
    expect(screen.getByRole("button", { name: "Record completed payout" })).toBeDisabled();
    confirm(); fireEvent.click(screen.getByRole("button", { name: "Record completed payout" }));
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ paid_at: "2026-01-18T10:00:00Z", amount_minor: 100 }));
    fireEvent.change(screen.getByLabelText("Amount (INR)"), { target: { value: "10.01" } }); confirm();
    expect(screen.getByRole("button", { name: "Record completed payout" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Amount (INR)"), { target: { value: "0.01" } });
    fireEvent.change(screen.getByLabelText("Paid at (UTC)"), { target: { value: "2099-01-18T10:00" } }); confirm();
    expect(screen.getByRole("button", { name: "Record completed payout" })).toBeDisabled();
  });
  it("replaces a chain amount instead of adding the old value twice", () => {
    render(<PayoutRecording scope={scope} payout={{ ...payout, remaining_minor: 0 }} amends={entry} />);
    fireEvent.change(screen.getByLabelText("Correction reason code"), { target: { value: "mistyped_amount" } }); confirm();
    expect(screen.getByRole("button", { name: "Append correction" })).toBeEnabled();
    fireEvent.change(screen.getByLabelText("Amount (INR)"), { target: { value: "2.01" } }); confirm();
    expect(screen.getByRole("button", { name: "Append correction" })).toBeDisabled();
  });
  it("takes a decimal amount, shows an amended amount as a decimal and refuses extra decimals", () => {
    const view = render(<PayoutRecording scope={scope} payout={payout} amends={entry} />);
    expect(screen.getByLabelText("Amount (INR)")).toHaveValue("2.00");
    view.unmount();
    render(<PayoutRecording scope={scope} payout={payout} />); fill();
    fireEvent.change(screen.getByLabelText("Amount (INR)"), { target: { value: "2.505" } }); confirm();
    expect(screen.getByRole("button", { name: "Record completed payout" })).toBeDisabled();
  });
  it("fails closed without server actions, including on amendment tips", () => {
    const view = render(<PayoutRecording scope={scope} payout={{ ...payout, allowed_actions: undefined }} />);
    expect(screen.queryByRole("button")).toBeNull();
    view.rerender(<PayoutRecording scope={scope} payout={payout} amends={{ ...entry, allowed_actions: [] }} />);
    expect(screen.queryByRole("button")).toBeNull();
  });
  it("preserves microseconds for a reference-only correction", () => {
    render(<PayoutRecording scope={scope} payout={payout} amends={{ ...entry, paid_at: "2026-01-18T10:00:01.123456Z" }} />);
    fireEvent.change(screen.getByLabelText("Correction reason code"), { target: { value: "reference_typo" } }); confirm();
    fireEvent.click(screen.getByRole("button", { name: "Append correction" }));
    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ paid_at: "2026-01-18T10:00:01.123456Z" }));
  });
});
