import { describe, expect, it } from "vitest";

import { AREA_CHARGE_ACTIONS, FINANCE_ONLY, SUBJECT_ACTION, ownsAreaCharges, ownsLoanCharges, paymentAccess } from "./paymentAccess";
import type { PaymentRow } from "./paymentsApi";

// Mutation-testing pins (decision 457): which action owns which charge subject, exactly as reconciliation_authority.SUBJECT_ACTIONS.
const EXPECTED: Record<string, string> = {
  machine_service_request: "manage_machines", booking: "manage_bookings", event_registration: "manage_events",
  makerspace_membership: "manage_makerspace", membership_term: "manage_makerspace", membership_request: "manage_members",
  membership_term_start: "manage_members", loan_deposit: "issue_request", loan_late_fee: "return_request",
  loan_rental: "return_request", loan_damage: "return_request", loan_lost: "return_request", machine_session: "manage_machines",
  event_order: "manage_events", event_venue_fee: "manage_events", donation: "manage_donations", sponsorship: "manage_donations",
  submission_fee: "manage_events", team_registration: "manage_events", event_deposit: "manage_events", shop_order: "manage_shop",
};
const row = (subject_type: string, status = "paid") => ({ subject_type, status }) as Pick<PaymentRow, "subject_type" | "status">;

describe("charge subject authority table", () => {
  it("maps every subject to exactly its owning action", () => {
    expect(SUBJECT_ACTION).toEqual(EXPECTED);
  });
  it("keeps gifts and sponsor money finance-only and the area actions to the rest, once each", () => {
    expect([...FINANCE_ONLY].sort()).toEqual(["donation", "sponsorship"]);
    expect([...AREA_CHARGE_ACTIONS].sort()).toEqual(["issue_request", "manage_bookings", "manage_events", "manage_machines", "manage_makerspace", "manage_members", "manage_shop", "return_request"]);
  });
});

describe("ownsLoanCharges / ownsAreaCharges", () => {
  it("loan money follows issue or return authority, either one", () => {
    expect(ownsLoanCharges(["issue_request"])).toBe(true);
    expect(ownsLoanCharges(["return_request"])).toBe(true);
    expect(ownsLoanCharges(["issue_request", "return_request"])).toBe(true);
    expect(ownsLoanCharges([])).toBe(false);
    expect(ownsLoanCharges(["manage_events", "record_payment"])).toBe(false);
  });
  it("an area queue exists for any area-charge action but not for finance-only or unrelated actions", () => {
    for (const action of AREA_CHARGE_ACTIONS) expect(ownsAreaCharges([action])).toBe(true);
    expect(ownsAreaCharges([])).toBe(false);
    expect(ownsAreaCharges(["manage_donations", "record_payment", "view_finance"])).toBe(false);
  });
});

describe("paymentAccess", () => {
  for (const [subject, action] of Object.entries(EXPECTED)) {

    const finance = subject === "donation" || subject === "sponsorship";
    it(`${subject}: the owner of ${action}, a record_payment holder, the superadmin and a stranger`, () => {
      for (const status of ["paid", "paid_offline"]) {
        expect(paymentAccess([action], false, row(subject, status))).toEqual({ record: true, waive: true, refund: !finance || status === "paid" });
        expect(paymentAccess([], true, row(subject, status))).toEqual({ record: true, waive: true, refund: true });
        expect(paymentAccess(["view_finance", "manage_nothing"], false, row(subject, status))).toEqual({ record: false, waive: false, refund: false });
      }
      // record_payment alone: may record, never waive; refunds need the subject authority except cash handed back offline.
      expect(paymentAccess(["record_payment"], false, row(subject, "paid"))).toEqual({ record: true, waive: false, refund: false });
      expect(paymentAccess(["record_payment"], false, row(subject, "paid_offline"))).toEqual({ record: true, waive: false, refund: true });
      // The wrong area's manager has no authority over this subject.
      const wrong = action === "manage_machines" ? "manage_bookings" : "manage_machines";
      expect(paymentAccess([wrong], false, row(subject, "paid_offline"))).toEqual({ record: false, waive: false, refund: false });
    });
  }

  it("an area manager's cash refund on an offline-paid charge of their own area, but never on gifts/sponsorship without record_payment", () => {
    expect(paymentAccess(["manage_donations"], false, row("donation", "paid_offline"))).toEqual({ record: true, waive: true, refund: false });
    expect(paymentAccess(["manage_donations"], false, row("sponsorship", "paid_offline"))).toEqual({ record: true, waive: true, refund: false });
    expect(paymentAccess(["manage_donations", "record_payment"], false, row("donation", "paid_offline"))).toEqual({ record: true, waive: true, refund: true });
    expect(paymentAccess(["manage_donations"], false, row("donation", "paid"))).toEqual({ record: true, waive: true, refund: true });
    expect(paymentAccess(["manage_events"], false, row("event_order", "paid_offline"))).toEqual({ record: true, waive: true, refund: true });
    expect(paymentAccess(["manage_events"], true, row("donation", "paid_offline"))).toEqual({ record: true, waive: true, refund: true });
  });
});
