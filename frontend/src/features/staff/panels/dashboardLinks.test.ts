import { setRouteSessionContext } from "../../../lib/api/sessionContext";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { dashboardHref } from "./dashboardLinks";
describe("dashboard drill-down URL state", () => {
  it.each([
    ["pending_requests", "requests?queue=pending"], ["awaiting_issue", "requests?queue=accepted"],
    ["open_booking_issues", "bookings?view=issues"],
    // Decision 224(a): the lending area's own lists, not the people area's accountability page.
    ["overdue_loans", "ledger?overdue=true"], ["open_problem_reports", "to-be-fixed?section=problems"],
    ["low_stock", "inventory?out_of_stock=true&archived=all"], ["pending_payments", "payments?status=pending"],
    ["stocktakes_awaiting_approval", "stocktake?status=completed"], ["failed_emails", "email-log?status=failed&recent_days=7"],
    ["pending_prints", "machines?work_queue=pending_prints"], ["active_prints", "machines?work_queue=active_prints"],
    ["prints_awaiting_collection", "machines?work_queue=prints_awaiting_collection"], ["maintenance_overdue", "machines?work_queue=maintenance_overdue"],
  ])("links %s to its filtered destination", (key, suffix) => {
    expect(dashboardHref(key, "forge")).toBe(`/m/forge/admin/${suffix}`);
    expect(dashboardHref(key, "forge", true)).toBe(`/admin/${suffix}`);
  });
  it("sets an inclusive thirty-day warranty cutoff", () => {
    expect(dashboardHref("warranty_expiring", "forge", false, false, new Date(2026, 9, 11))).toBe("/m/forge/admin/warranty?expires_before=2026-11-10");
  });
});

beforeEach(() => setRouteSessionContext("person"));
afterEach(() => setRouteSessionContext("person"));

it("keeps person links plain and the platform context explicit on chart drill-down", () => {
  setRouteSessionContext("person");
  expect(dashboardHref("pending_payments", "forge")).toBe("/m/forge/admin/payments?status=pending");
  setRouteSessionContext("platform");
  expect(dashboardHref("failed_emails", "forge")).toBe("/admin/email-log?status=failed&recent_days=7&context=platform");
});
