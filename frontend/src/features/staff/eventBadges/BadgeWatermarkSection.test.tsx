import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it, vi } from "vitest";

vi.mock("zxing-wasm/writer", () => ({ setZXingModuleOverrides: vi.fn(), writeBarcode: vi.fn(async () => ({ image: null })) }));
vi.mock("../../../lib/api", () => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn(async () => new Blob()) }));

import { BadgeCanvas } from "./BadgeCanvas";
import { compileBadge } from "./badgeCompile";
import { exportBadgeFile, readBadgeFile } from "./badgeFile";
import { defaultSettings, normalizeSettings, type BadgeSettings } from "./badgeNormalize";
import { BadgeWatermarkSection } from "./BadgeWatermarkSection";

function Harness({ onChange }: { onChange: (settings: BadgeSettings) => void }) {
  const [settings, setSettings] = useState(defaultSettings("Night", "Space"));
  return <BadgeWatermarkSection settings={settings} update={(patch) => {
    const next = normalizeSettings({ ...settings, ...patch });
    if (patch.watermark) next.watermark.text = patch.watermark.text.slice(0, 32);
    setSettings(next); onChange(next);
  }} />;
}

it("sets a text watermark: text, strength, colour and angle, with image shown as unavailable", () => {
  let latest = defaultSettings();
  render(<Harness onChange={(settings) => { latest = settings; }} />);
  expect(screen.getByRole("radio", { name: "Image" })).toBeDisabled();
  expect(screen.queryByRole("textbox", { name: "Watermark text" })).toBeNull();
  fireEvent.click(screen.getByRole("radio", { name: "Text" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Watermark text" }), { target: { value: "crew only" } });
  fireEvent.change(screen.getByRole("spinbutton", { name: "Strength (%)" }), { target: { value: "50" } });
  fireEvent.click(screen.getByRole("radio", { name: "Text colour" }));
  fireEvent.change(screen.getByRole("spinbutton", { name: "Angle (°)" }), { target: { value: "15" } });
  expect(latest.watermark).toEqual({ kind: "text", text: "crew only", opacityPct: 30, colour: "text", angleDeg: 15 });
  fireEvent.click(screen.getByRole("radio", { name: "None" }));
  expect(latest.watermark.kind).toBe("none");
});

it("compiles, draws, exports and re-imports the watermark", () => {
  const settings = { ...defaultSettings("Night", "Space"),
    watermark: { kind: "text" as const, text: "staff", opacityPct: 12, colour: "accent" as const, angleDeg: -75 } };
  const compiled = compileBadge(settings);
  expect(compiled.watermark).toMatchObject({ kind: "text", text: "STAFF", opacity_pct: 12, angle_deg: -60, colour: "#006E63" });
  render(<BadgeCanvas settings={settings} values={{ name: "Priya" }} pxPerMm={2} designId={1} />);
  expect(screen.getByText("STAFF")).toBeInTheDocument();
  const read = readBadgeFile(exportBadgeFile(settings));
  expect("file" in read && normalizeSettings(read.file.settings).watermark).toEqual(settings.watermark);
});

it("an Events image watermark falls back to no watermark on the badge", () => {
  const settings = normalizeSettings({ colorMode: "colour", watermark: { kind: "image", opacityPct: 10 } });
  expect(compileBadge(settings).watermark.kind).toBe("none");
});
