import { useState } from "react";
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { defaultStageSettings, StageSettingsFields } from "./StageSettingsFields";
function Editor() {
  const [value, setValue] = useState(defaultStageSettings());
  return <><StageSettingsFields value={value} onChange={setValue} canBlock={false} /><output data-testid="settings">{JSON.stringify(value)}</output></>;
}
describe("stage timing and immediate edit tracking", () => {
  it("clears inactive deadline columns as mode changes", () => {
    render(<Editor />);
    fireEvent.change(screen.getByLabelText("Deadline schedule"), { target: { value: "event_end" } });
    let settings = JSON.parse(screen.getByTestId("settings").textContent!);
    expect(settings).toMatchObject({ due_mode: "event_end", due_after_seconds: null, due_at: null, due_event_offset_seconds: 0 });
    fireEvent.change(screen.getByLabelText("Stage"), { target: { value: "accepted_rsvp" } });
    expect(screen.getByLabelText("Activation point")).toHaveValue("accepted");
    fireEvent.change(screen.getByLabelText("Stage"), { target: { value: "post_event" } });
    settings = JSON.parse(screen.getByTestId("settings").textContent!);
    expect(settings.activation_point).toBe("");
    expect(screen.getByRole("option", { name: "Block configured later actions" })).toBeDisabled();
  });
  it("updates audience and reminders before blur so navigation cannot lose untracked edits", () => {
    render(<Editor />);
    fireEvent.change(screen.getByLabelText("Audience track IDs"), { target: { value: "3, 7" } });
    fireEvent.change(screen.getByLabelText("Reminder offsets in seconds"), { target: { value: "-3600, -60" } });
    const settings = JSON.parse(screen.getByTestId("settings").textContent!);
    expect(settings.audience.track_ids).toEqual([3, 7]); expect(settings.reminder_offsets).toEqual([-3600, -60]);
  });
});
