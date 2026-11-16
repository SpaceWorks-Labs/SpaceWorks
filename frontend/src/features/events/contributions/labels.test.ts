import { describe, expect, it } from "vitest";
import { contributionRoleLabel, contributionStateLabel, shiftActionLabel, shiftAttendanceLabel } from "./labels";

describe("contribution wording", () => {
  it.each([
    ["co_organizer", "Co-organizer"], ["volunteer", "Volunteer"], ["mentor", "Mentor"], ["judge", "Judge"], ["sponsor_rep", "Sponsor representative"],
  ])("role %s reads %s", (role, label) => expect(contributionRoleLabel(role)).toBe(label));
  it("falls back to the spaced code for an unknown role", () => expect(contributionRoleLabel("guest_speaker")).toBe("guest speaker"));

  it.each([
    ["draft", "Draft"], ["proposed", "Proposed"], ["applied", "Applied"], ["waitlisted", "Waitlisted"], ["approved", "Approved"],
    ["declined", "Declined"], ["withdrawn", "Withdrawn"], ["revoked", "Revoked"], ["completed", "Completed"],
  ])("state %s reads %s", (state, label) => expect(contributionStateLabel(state)).toBe(label));
  it("falls back to the spaced code for an unknown state", () => expect(contributionStateLabel("on_hold")).toBe("on hold"));

  it.each([["scheduled", "Scheduled"], ["checked_in", "Checked in"], ["checked_out", "Checked out"], ["no_show", "No-show"]])(
    "attendance %s reads %s", (state, label) => expect(shiftAttendanceLabel(state)).toBe(label));
  it("falls back for an unknown attendance state", () => expect(shiftAttendanceLabel("late_arrival")).toBe("late arrival"));

  it.each([
    ["withdraw", "Withdraw"], ["check-in", "Check in"], ["check-out", "Check out"], ["approve", "Approve"],
    ["verify-hours", "Verify hours"], ["adjust-hours", "Adjust hours"],
  ])("action %s reads %s", (action, label) => expect(shiftActionLabel(action)).toBe(label));
  it("falls back for an unknown action, replacing both dashes and underscores", () => expect(shiftActionLabel("swap-shift_now")).toBe("swap shift now"));
});
