import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SettingsEditorActions } from "./SettingsEditorActions";

describe("independent settings actions", () => {
  it("only offers Save and Discard after this editor changes", () => {
    const discard = vi.fn();
    const save = vi.fn();
    const view = render(<SettingsEditorActions dirty={false} onDiscard={discard} onSave={save} />);
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
    view.rerender(<SettingsEditorActions dirty onDiscard={discard} onSave={save} />);
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(discard).toHaveBeenCalledOnce();
    expect(save).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(save).toHaveBeenCalledOnce();
  });

  it("blocks both actions during this editor's save", () => {
    render(<SettingsEditorActions dirty pending onDiscard={vi.fn()} onSave={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Discard" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Saving/ })).toBeDisabled();
  });
});
