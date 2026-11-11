import { describe, expect, it } from "vitest";

import { exportBadgeFile, readBadgeFile } from "./badgeFile";
import { normalizeSettings } from "./badgeNormalize";

const settings = { widthMm: 101.6, heightMm: 152.4, template: "bold", colorMode: "colour", heading: "Build Night" };

describe("badge design files", () => {
  it.each(["swe-id-card-design", "yuyu-id-card-design"])("accepts the SpaceWorks-Events kind %s as written, any version", (kind) => {
    const read = readBadgeFile(JSON.stringify({ kind, version: 7, settings }));
    expect(read).toEqual({ file: { kind, version: 7, settings } });
  });

  it("round-trips its own export", () => {
    const normalized = normalizeSettings(settings, "Build Night", "Tinkerspace");
    const read = readBadgeFile(exportBadgeFile(normalized));
    expect("file" in read && read.file.kind).toBe("spaceworks-event-badge");
    expect("file" in read && normalizeSettings(read.file.settings, "Build Night", "Tinkerspace")).toEqual(normalized);
  });

  it("refuses a newer SpaceWorks file, a non-badge file and broken JSON", () => {
    expect(readBadgeFile(JSON.stringify({ kind: "spaceworks-event-badge", version: 2, settings }))).toEqual({ problem: "newer" });
    expect(readBadgeFile(JSON.stringify({ kind: "card-design", settings }))).toEqual({ problem: "not_badge" });
    expect(readBadgeFile(JSON.stringify({ kind: "swe-id-card-design", settings: [] }))).toEqual({ problem: "not_badge" });
    expect(readBadgeFile("{not json")).toEqual({ problem: "not_badge" });
  });

  it("refuses files over 200 000 bytes before parsing", () => {
    expect(readBadgeFile(`{"kind":"swe-id-card-design","settings":{"heading":"${"x".repeat(200_001)}"}}`)).toEqual({ problem: "too_large" });
  });

  it("a legacy Events file without colorMode opens in black and white with optional items off", () => {
    const legacy = normalizeSettings({ widthMm: 105, heightMm: 148, showEmail: true, template: "bold" });
    expect(legacy.colorMode).toBe("mono");
    expect(legacy.showSymbol).toBe(false);
  });
});
