import { describe, expect, it } from "vitest";

import { getStaffAccess } from "./staffAccess";
import { paymentAccess } from "./paymentAccess";
import { paymentListKey, paymentListPath, type PaymentRow } from "./paymentsApi";

describe("member and finance delegation", () => {
  it("opens roster and cards without settings or money", () => {
    const access = getStaffAccess(["manage_members"], false, false);
    expect(access.allowedTabs).toContain("members");
    expect(access.allowedTabs).toContain("cards");
    expect(access.allowedTabs).not.toContain("settings");
    expect(access.allowedTabs).not.toContain("users");
    // Decision 242(a): manage_members owns guest-pass charges, so it opens the own-area payments queue.
    expect(access.allowedTabs).toContain("payments");
  });

  it("opens finance reports and ledger independently of roster", () => {
    const access = getStaffAccess(["view_finance"], false, false);
    expect(access.allowedTabs).toContain("payments");
    expect(access.allowedTabs).toContain("reports");
    expect(access.allowedTabs).not.toContain("members");
    expect(access.allowedTabs).not.toContain("settings");
  });

  it("keeps cashiers in the handover console with a payments tab", () => {
    const actions = ["record_payment", "view_inventory", "assign_box", "issue_request", "issue_direct_loan", "return_request", "upload_evidence", "collect_service_request"];
    const access = getStaffAccess(actions, false, false);
    expect(access.handoutOnly).toBe(true);
    expect(access.allowedTabs).toEqual(["dashboard", "requests", "direct", "handover", "payments", "notifications", "channels", "ledger"]);
    expect(getStaffAccess(["record_payment"], false, false).defaultTab).toBe("dashboard");
  });

  it("opens the payments tab for an Event Manager without finance actions", () => {
    const access = getStaffAccess(["manage_events"], false, false);
    expect(access.canViewFinance).toBe(false);
    expect(access.canRecordPayment).toBe(false);
    expect(access.handoutOnly).toBe(false);
    expect(access.allowedTabs).toContain("events");
    expect(access.allowedTabs).toContain("payments");
    // #219(e-1): the area audit log opens without view_audit; view_audit-only tabs do not.
    expect(access.allowedTabs).toContain("audit");
    expect(access.allowedTabs).not.toContain("accountability");
  });

  it("lets an Event Manager reconcile event charges but not provider-refund cash", () => {
    const row = { subject_type: "event_registration", status: "pending" } as PaymentRow;
    expect(paymentAccess(["manage_events"], false, row)).toEqual({ record: true, waive: true, refund: true });
    // Decision 242(c): the area's own manager also hands back cash on an offline-paid charge of their area.
    expect(paymentAccess(["manage_events"], false, { ...row, status: "paid_offline" }).refund).toBe(true);
    expect(paymentAccess(["manage_events"], false, { ...row, subject_type: "booking" })).toEqual({ record: false, waive: false, refund: false });
  });

  it("does not infer narrower grants from settings administration", () => {
    const access = getStaffAccess(["manage_makerspace"], false, false);
    expect(access.allowedTabs).not.toContain("members");
    // manage_makerspace owns membership-fee charges (decision 242(a)), so payments opens; roster does not.
    expect(access.allowedTabs).toContain("payments");
  });

  it("separates counter queries from ledger queries in the cache", () => {
    expect(paymentListPath(7, "pending", "", true)).toContain("for_recording=true");
    expect(paymentListKey(7, "pending", "", true)).not.toEqual(paymentListKey(7, "pending", ""));
  });

  it("keeps read-only finance free of mutation controls", () => {
    const row = { subject_type: "booking", status: "pending" } as PaymentRow;
    expect(paymentAccess(["view_finance"], false, row)).toEqual({ record: false, waive: false, refund: false });
    expect(paymentAccess(["record_payment"], false, row)).toEqual({ record: true, waive: false, refund: false });
    expect(paymentAccess(["record_payment"], false, { ...row, status: "paid_offline" }).refund).toBe(true);
    expect(paymentAccess(["manage_bookings"], false, row).waive).toBe(true);
  });
});
