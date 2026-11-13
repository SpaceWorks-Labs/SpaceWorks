import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OriginalVideo } from "./OriginalVideo";

describe("verified original video", () => {
  it("does not fetch an unsupported codec and keeps the original download available", () => {
    const load = vi.fn(), download = vi.fn();
    render(<OriginalVideo bytes={100} playable={false} load={load} download={download} />);
    expect(screen.queryByRole("button", { name: "Load original video" })).toBeNull();
    expect(load).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Download original video" }));
    expect(download).toHaveBeenCalledOnce();
  });
  it("requires explicit confirmation before loading a large original", () => {
    const load = vi.fn();
    render(<OriginalVideo bytes={100 * 1024 ** 2} playable load={load} download={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Load original video" }));
    expect(load).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(load).not.toHaveBeenCalled();
  });
});
