import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RoundSettingsFields } from "./RoundSettingsFields";

describe("round feedback and reminder switches (S4, S15)", () => {
  it("are off by default and change independently", () => {
    const change = vi.fn();
    render(<RoundSettingsFields value={{ visibility: "assigned", fresh_eyes: false, panel: "" }} onChange={change} />);
    const share = screen.getByLabelText(/Share judges/) as HTMLInputElement;
    const remind = screen.getByLabelText(/Remind judges with unfinished assignments/) as HTMLInputElement;
    expect(share.checked).toBe(false);
    expect(remind.checked).toBe(false);
    fireEvent.click(share);
    expect(change).toHaveBeenLastCalledWith(expect.objectContaining({ share_feedback: true }));
    fireEvent.click(remind);
    expect(change).toHaveBeenLastCalledWith(expect.objectContaining({ judge_reminders: true }));
  });
});
