import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

vi.mock("zxing-wasm/writer", () => ({ setZXingModuleOverrides: vi.fn(), writeBarcode: vi.fn(async () => ({ image: null })) }));
vi.mock("../../../lib/api", () => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn(async () => new Blob()) }));

import { BadgeCanvas } from "./BadgeCanvas";
import { compileBadge } from "./badgeCompile";
import { defaultSettings } from "./badgeNormalize";

const settings = { ...defaultSettings("Build Night", "Tinkerspace"), gridSizeMm: 2 as const };
const values = { name: "Priya Raman", email: "priya@example.com" };

it("draws every compiled layer and the sample name", () => {
  const { container } = render(<BadgeCanvas settings={settings} values={values} pxPerMm={2} designId={1} />);
  expect(container.querySelectorAll("[data-badge-preview] > div[aria-hidden]")).toHaveLength(compileBadge(settings).layers.length);
  expect(screen.getByText("Priya Raman")).toBeInTheDocument();
  expect(screen.queryByRole("button")).toBeNull();
});

it("arrow keys nudge the selected item by one grid step, Shift by five", () => {
  const onMove = vi.fn(), onBeginChange = vi.fn();
  render(<BadgeCanvas settings={settings} values={values} pxPerMm={2} designId={1}
    interaction={{ selected: "name", onSelect: vi.fn(), onBeginChange, onMove, showGrid: true }} />);
  const name = screen.getByRole("button", { name: /^Attendee name\./ });
  const at = settings.elementPositions.name;
  fireEvent.keyDown(name, { key: "ArrowRight" });
  expect(onMove).toHaveBeenLastCalledWith("name", at.xMm + 2, at.yMm);
  fireEvent.keyDown(name, { key: "ArrowDown", shiftKey: true });
  expect(onMove).toHaveBeenLastCalledWith("name", at.xMm, at.yMm + 10);
  expect(onBeginChange).toHaveBeenCalledTimes(2);
});

it("dragging converts pointer pixels to millimetres", () => {
  const onMove = vi.fn();
  render(<BadgeCanvas settings={settings} values={values} pxPerMm={2} designId={1}
    interaction={{ selected: null, onSelect: vi.fn(), onBeginChange: vi.fn(), onMove, showGrid: false }} />);
  const qr = screen.getByRole("button", { name: /^Check-in QR\./ });
  fireEvent.pointerDown(qr, { button: 0, clientX: 100, clientY: 100, pointerId: 1 });
  fireEvent.pointerMove(qr, { clientX: 80, clientY: 120, pointerId: 1 });
  const at = settings.elementPositions.qr;
  expect(onMove).toHaveBeenLastCalledWith("qr", at.xMm - 10, at.yMm + 10);
});
