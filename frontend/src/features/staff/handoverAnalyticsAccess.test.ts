import { expect, it } from "vitest";
import { getStaffAccess } from "./staffAccess";
import { sidebarSections } from "./sidebarSections";
import { visibleRequestTabs } from "./panels/requestTabs";

it("makes the queue home the handover landing page without granting reports", () => {
  const actions = ["view_inventory", "issue_request", "return_request", "upload_evidence", "collect_service_request"];
  const access = getStaffAccess(actions, false, false);
  expect(access.handoutOnly).toBe(true);
  expect(access.defaultTab).toBe("dashboard");
  expect(access.allowedTabs).toContain("dashboard");
  expect(access.allowedTabs).not.toContain("reports");
  const sections = sidebarSections(access.allowedTabs, "dashboard", key => `/admin/${key}`, () => {}, true);
  expect(sections[0].items[0].key).toBe("dashboard");
});

it("keeps the home reachable for a collecting-only handover actor", () => {
  const access = getStaffAccess(["collect_service_request"], false, false);
  expect(access.allowedTabs).toContain("dashboard");
  expect(access.defaultTab).toBe("dashboard");
  expect(access.allowedTabs).not.toContain("requests");
});

it("allows the active-loans destination in handover navigation under the server's queue action", () => {
  expect(visibleRequestTabs(true, ["issue_request", "return_request"])).toEqual(["accepted", "active", "history"]);
  expect(visibleRequestTabs(true, ["return_request"])).toEqual([]);
  expect(visibleRequestTabs(true, ["accept_request"])).not.toContain("pending");
});
