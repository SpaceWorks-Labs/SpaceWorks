import { describe, expect, it } from "vitest";
import { isEventAddonPath, memberEventAddonHref } from "./routeNames";
import { isProgrammePath } from "../programme/routeNames";
import { eventDrawerSurfaces } from "../../staff/eventDrawerTabs";
import { eventAccess } from "../../staff/eventStaffPermissions";

describe("member event add-on routes", () => {
  it("matches the exact links backend notices write", () => {
    for (const path of ["/member/events/12/reimbursement", "/member/events/12/reimbursement/claim", "/m/space/member/events/12/stage-forms",
      "/member/events/12/stage-forms/4", "/member/events/12/stage-responses/9", "/member/event-payouts",
      "/member/event-payouts/7c9e6679-7425-40de-944b-e07fc1f90ae7"]) expect(isEventAddonPath(path)).toBe(true);
  });
  it("leaves ticket, history and programme routes alone", () => {
    for (const path of ["/member/events/12/ticket", "/member/events/history", "/member/events/12/reimbursement/other",
      "/member/event-payouts/not-a-uuid"]) expect(isEventAddonPath(path)).toBe(false);
    expect(isProgrammePath("/member/events/12/reimbursement")).toBe(false);
  });
  it("builds tenant-prefixed hrefs", () => {
    expect(memberEventAddonHref("my space", 3, "reimbursement/claim")).toBe("/m/my%20space/member/events/3/reimbursement/claim");
    expect(memberEventAddonHref("", 3, "stage-forms")).toBe("/member/events/3/stage-forms");
  });
});

describe("event drawer add-on sections", () => {
  const event = { status: "published", ticketing_features: [], report_features: [] } as never;
  it("gates travel support on the module and the screening grant", () => {
    const reviewer = eventAccess({ staff_permissions: ["review_reimbursements"], can_manage_staff: false });
    expect(eventDrawerSurfaces(event, reviewer, [], []).sections.reimbursements).toBe(false);
    expect(eventDrawerSurfaces(event, reviewer, [], ["event_reimbursements"]).sections.reimbursements).toBe(true);
    const checkIn = eventAccess({ staff_permissions: ["check_in"], can_manage_staff: false });
    expect(eventDrawerSurfaces(event, checkIn, [], ["event_reimbursements"]).sections.reimbursements).toBe(false);
  });
  it("shows stage forms to editors and registration managers only", () => {
    expect(eventDrawerSurfaces(event, eventAccess({ staff_permissions: ["edit_details"], can_manage_staff: false })).sections["stage-forms"]).toBe(true);
    expect(eventDrawerSurfaces(event, eventAccess({ staff_permissions: ["check_in"], can_manage_staff: false })).sections["stage-forms"]).toBe(false);
  });
});
