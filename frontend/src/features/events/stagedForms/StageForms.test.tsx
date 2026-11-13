import { describe, expect, it } from "vitest";
import { stageDueState } from "./StageForms";
import type { StageAssignment } from "./types";

const assignment: StageAssignment = { id: 1, stage_form_id: 2, title: "Travel follow-up", version: 1, state: "open",
  due_at: "2026-10-20T12:00:00Z", opens_at: "2026-10-18T12:00:00Z", due_revision: 1,
  required: true, pinned_form_revision_id: 10, response_id: 20, response_version: 1, blocked_actions: ["claim_submit"] };

describe("stage deadline display", () => {
  it("closes at the exact server deadline even before a worker updates state", () => {
    expect(stageDueState(assignment, Date.parse(assignment.due_at))).toBe("overdue");
    expect(stageDueState(assignment, Date.parse(assignment.due_at) - 1)).toBe("open");
  });
  it("does not show cancelled or submitted work as overdue", () => {
    expect(stageDueState({ ...assignment, state: "cancelled" }, Date.parse(assignment.due_at) + 1)).toBe("cancelled");
    expect(stageDueState({ ...assignment, state: "completed" }, Date.parse(assignment.due_at) + 1)).toBe("completed");
  });
  it("uses absolute offsets instead of the browser timezone", () => {
    expect(stageDueState({ ...assignment, due_at: "2026-10-20T17:30:00+05:30" }, Date.parse("2026-10-20T12:00:00Z"))).toBe("overdue");
  });
});
