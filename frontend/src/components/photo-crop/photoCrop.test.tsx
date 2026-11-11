import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { baseFrame, clampView, cropRect, initialView, MAX_ZOOM, outputSize, pan, zoomTo } from "./cropMath";
import { PhotoPicker } from "./PhotoPicker";

describe("crop maths", () => {
  it("fits the largest frame of the card's aspect inside the picture", () => {
    expect(baseFrame(1000, 1000, 0.5)).toEqual({ width: 500, height: 1000 });
    expect(baseFrame(1000, 400, 1)).toEqual({ width: 400, height: 400 });
  });

  it("keeps the frame inside the picture at every zoom and pan", () => {
    const view = initialView(800, 600);
    const rect = cropRect(view, 800, 600, 1);
    expect(rect).toEqual({ sx: 100, sy: 0, sw: 600, sh: 600 });
    const panned = pan(view, 10_000, 10_000, 280, 800, 600, 1);
    expect(cropRect(panned, 800, 600, 1).sx).toBe(0);
    const zoomed = zoomTo(view, 99, 800, 600, 1);
    expect(zoomed.zoom).toBe(MAX_ZOOM);
    const far = clampView({ zoom: 2, cx: 10_000, cy: -5 }, 800, 600, 1);
    const farRect = cropRect(far, 800, 600, 1);
    expect(farRect.sx + farRect.sw).toBeCloseTo(800);
    expect(farRect.sy).toBeCloseTo(0);
  });

  it("dragging right moves the frame left (the picture follows the finger)", () => {
    const view = zoomTo(initialView(1000, 1000), 2, 1000, 1000, 1);
    expect(pan(view, 28, 0, 280, 1000, 1000, 1).cx).toBeLessThan(view.cx);
  });

  it("never outputs more than 1200 px on the long side", () => {
    expect(outputSize({ sx: 0, sy: 0, sw: 3000, sh: 1500 })).toEqual({ width: 1200, height: 600 });
    expect(outputSize({ sx: 0, sy: 0, sw: 300, sh: 400 })).toEqual({ width: 300, height: 400 });
  });
});

describe("PhotoPicker", () => {
  it("opens the crop step for a chosen file and never hands back the uncropped file on cancel", () => {
    const onPhoto = vi.fn();
    vi.stubGlobal("URL", class extends URL { static createObjectURL() { return "blob:photo"; } static revokeObjectURL() {} });
    render(<PhotoPicker aspect={0.8} onPhoto={onPhoto} />);
    const input = screen.getByLabelText("Choose a photo") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], "me.png", { type: "image/png" })] } });
    expect(screen.getByRole("dialog", { name: "Crop the photo" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Use this photo" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onPhoto).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog", { name: "Crop the photo" })).not.toBeInTheDocument();
  });

  it("is disabled until consent is given", () => {
    render(<PhotoPicker aspect={1} disabled onPhoto={vi.fn()} />);
    expect(screen.getByLabelText("Choose a photo")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Take a photo" })).toBeDisabled();
  });
});
