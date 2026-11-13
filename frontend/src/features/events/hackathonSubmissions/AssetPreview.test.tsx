import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../../test/axe";
import { AssetPreview } from "./AssetPreview";
import { ASK_PREVIEW_BYTES, MAX_PREVIEW_MS } from "./previewBounds";

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe("lazy maker previews", () => {
  it("does not download anything until requested and asks again for large files", async () => {
    const load = vi.fn();
    const { container } = render(<AssetPreview assetId={1} bytes={ASK_PREVIEW_BYTES} filename="project.step"
      extension="step" load={load} download={() => {}} />);
    expect(load).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Load preview" }));
    expect(load).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Load large preview" })).toBeTruthy();
    await expectNoA11yViolations(container);
  });
  it("times out a stuck parser and preserves original download", async () => {
    vi.useFakeTimers();
    const terminate = vi.fn(), postMessage = vi.fn(), download = vi.fn();
    class PreviewWorker { terminate = terminate; postMessage = postMessage; }
    vi.stubGlobal("Worker", PreviewWorker);
    const load = vi.fn().mockResolvedValue({ size: 4, arrayBuffer: async () => new ArrayBuffer(4) });
    render(<AssetPreview assetId={1} bytes={4} filename="project.stl" extension="stl" load={load} download={download} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Load preview" })); });
    expect(postMessage).toHaveBeenCalledOnce();
    await act(async () => { vi.advanceTimersByTime(MAX_PREVIEW_MS); });
    expect(terminate).toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("Preview unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Download original" }));
    expect(download).toHaveBeenCalledOnce();
  });
  it("cancel aborts a pending read without showing an error", async () => {
    let signal: AbortSignal | undefined;
    const load = vi.fn((value: AbortSignal) => { signal = value; return new Promise<Blob>(() => {}); });
    render(<AssetPreview assetId={1} bytes={4} filename="project.stl" extension="stl" load={load} download={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Load preview" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel preview" }));
    expect(signal?.aborted).toBe(true);
    expect(screen.queryByText(/Preview unavailable/)).toBeNull();
    expect(screen.getByRole("button", { name: "Load preview" })).toBeTruthy();
  });
});
