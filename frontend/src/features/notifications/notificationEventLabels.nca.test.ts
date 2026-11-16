import { describe, expect, it } from "vitest";
import { notificationEventLabel } from "./notificationEventLabels";

// NCA audit 0.12.0: these catalogue events fell back to their raw code ("shop order new") before.
describe("notificationEventLabel", () => {
  it.each([
    ["shop_order_new", "New shop order"],
    ["guest_pass_issued", "Guest pass issued"],
    ["room_outage", "Room out of service"],
    ["stage_promoted", "Moved to the next stage"],
    ["adapter_job_review", "Job report waiting for review"],
  ])("labels %s", (event, label) => {
    expect(notificationEventLabel(event)).toBe(label);
  });

  it("still falls back readably for an unknown code", () => {
    expect(notificationEventLabel("brand_new.thing")).toBe("brand new thing");
  });
});
