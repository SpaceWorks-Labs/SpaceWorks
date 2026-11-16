import { describe, expect, it } from "vitest";
import { backupArchiveStatusLabel, deploymentRestoreStageLabel, spaceRestoreStageLabel } from "./backupLabels";

describe("backup wording", () => {
  it.each([
    ["pending", "Pending"], ["running", "Running"], ["promoting", "Finishing"], ["available", "Available"],
    ["failed", "Failed"], ["expired", "Expired"],
  ])("archive status %s reads %s", (status, label) => expect(backupArchiveStatusLabel(status)).toBe(label));
  it("humanizes an unknown archive status instead of showing the raw code", () => expect(backupArchiveStatusLabel("half_done_state")).toBe("half done state"));

  it.each([
    ["requested", "Requested"], ["staging", "Preparing preview"], ["preview_ready", "Preview ready"], ["applying", "Restoring"],
    ["completed", "Completed"], ["failed", "Failed"], ["aborted", "Cancelled"],
  ])("space restore stage %s reads %s", (stage, label) => expect(spaceRestoreStageLabel(stage)).toBe(label));
  it("humanizes an unknown space restore stage", () => expect(spaceRestoreStageLabel("new_stage")).toBe("new stage"));

  it.each([
    ["requested", "Requested"], ["claimed", "Claimed"], ["preflight", "Checking"], ["quiesced", "Paused for your decision"],
    ["db_restoring", "Restoring the database"], ["objects_restoring", "Restoring files"], ["validating", "Validating"],
    ["completed", "Completed"], ["restored_quarantined", "Restored, held for review"], ["rolling_back", "Rolling back"],
    ["failed", "Failed"], ["aborted", "Cancelled"],
  ])("platform restore stage %s reads %s", (stage, label) => expect(deploymentRestoreStageLabel(stage)).toBe(label));
  it("humanizes an unknown platform restore stage", () => expect(deploymentRestoreStageLabel("some_new_stage")).toBe("some new stage"));
});
