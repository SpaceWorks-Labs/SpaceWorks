import { describe, expect, it } from "vitest";
import { StructuredApiError } from "../../../../../lib/api/errors";
import { adapterErrorMessage, capabilityLabel, controlLabel, stateLabel, stateTone, targetTypeLabel } from "./adapterCopy";

const err = (code: string, body: Record<string, unknown> = {}) => new StructuredApiError(409, { code, ...body } as never);

describe("adapterErrorMessage", () => {
  it.each([
    ["adapter_watch_streams_quota_reached", "Too many camera watches are open at once. End one, or wait for it to expire, then try again."],
    ["adapter_snapshots_quota_reached", "This space has used all the camera snapshots its plan allows this month."],
    ["binding_exists", "That target is already bound to this adapter."],
    ["adapter_revoked", "This adapter has been revoked and can no longer be used."],
    ["capability_missing", "This target does not offer that action."],
    ["capability_not_declared", "The adapter has not said it can do that yet. Let it connect once, then try again."],
    ["capability_target_mismatch", "That capability cannot work with this kind of target."],
    ["command_unknown", "The adapter does not know that command."],
    ["pose_not_calibrated", "No position is saved for that place yet. Calibrate it first."],
    ["invalid_pose", "That position is not valid. Use numbers only."],
    ["watch_ended", "That camera watch has already ended. Start a new one."],
    ["credential_in_use", "That credential is already in use by someone else."],
    ["invalid_pin", "A PIN is 6 to 12 digits."],
    ["weak_pin", "That PIN is too easy to guess. Choose another."],
    ["adapter_unavailable", "The adapter is offline right now, so the command was not sent."],
  ])("%s reads in plain words", (code, text) => expect(adapterErrorMessage(err(code))).toBe(text));
  it("names the bridge limit when the server sends one, as a number or a string", () => {
    const withLimit = "This space already has the 5 bridges its plan allows. Revoke one you no longer use, or ask the platform operator to raise the limit.";
    expect(adapterErrorMessage(err("adapter_bridges_quota_reached", { limit: 5 }))).toBe(withLimit);
    expect(adapterErrorMessage(err("adapter_bridges_quota_reached", { limit: "5" }))).toBe(withLimit);
  });
  it("uses the no-number sentence when the limit is missing or of another type", () => {
    const without = "This space has reached the number of bridges its plan allows. Revoke one you no longer use, or ask the platform operator to raise the limit.";
    expect(adapterErrorMessage(err("adapter_bridges_quota_reached"))).toBe(without);
    expect(adapterErrorMessage(err("adapter_bridges_quota_reached", { limit: { n: 1 } }))).toBe(without);
  });
  it("passes an unknown code through as the error's own message", () => {
    const e = err("something_new", { detail: "Custom detail" });
    expect(adapterErrorMessage(e)).toBe(e.message);
  });
  it("uses a plain Error's message and a generic line for anything else", () => {
    expect(adapterErrorMessage(new Error("offline"))).toBe("offline");
    expect(adapterErrorMessage(42)).toBe("Something went wrong. Try again.");
  });
});

describe("binding state", () => {
  it.each([["idle", "Idle"], ["preparing", "Preparing"], ["running", "Running"], ["paused", "Paused"], ["finished", "Finished"], ["failed", "Failed"],
    ["error", "Error"], ["offline", "Offline"], ["maintenance", "Maintenance"], [undefined, "No report yet"]] as const)("state %s reads %s", (state, label) => expect(stateLabel(state)).toBe(label));
  it.each([["running", "success"], ["finished", "success"], ["failed", "danger"], ["error", "danger"], ["paused", "warn"], ["preparing", "warn"],
    ["maintenance", "warn"], ["offline", "warn"], ["idle", "neutral"], [undefined, "neutral"]] as const)("state %s is tone %s", (state, tone) => expect(stateTone(state)).toBe(tone));
});

describe("other wording", () => {
  it.each([["machine", "Machine"], ["machine_type", "Machine type"], ["storage_location", "Storage location"], ["item", "Item"], ["box", "Box"], ["door", "Door"],
    ["space", "Space"], ["gadget", "gadget"]])("target type %s reads %s", (type, label) => expect(targetTypeLabel(type)).toBe(label));
  it.each([["pause", "Pause"], ["resume", "Resume"], ["cancel", "Cancel job"], ["power", "Power"], ["reboot", "reboot"]])("command %s reads %s", (command, label) => expect(controlLabel(command)).toBe(label));
  it("spells a capability name with spaces, from a string or an object", () => {
    expect(capabilityLabel("camera.snapshot_now")).toBe("camera snapshot now");
    expect(capabilityLabel({ name: "job.pause" } as never)).toBe("job pause");
  });
});
