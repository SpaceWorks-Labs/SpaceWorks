// Badge design files: {kind, version, settings}. SpaceWorks writes `spaceworks-event-badge` v1 and accepts the
// SpaceWorks-Events kinds (`swe-id-card-design`, any version, and its older name `yuyu-id-card-design`) as
// they were written. This is the quick check before upload; the server parses again, normalises and reports
// what did not survive (backend apps/card_designs/badge_import.py).
import type { BadgeSettings } from "./badgeNormalize";

export const BADGE_FILE_KIND = "spaceworks-event-badge";
export const EVENTS_FILE_KINDS = ["swe-id-card-design", "yuyu-id-card-design"] as const;
export const MAX_FILE_BYTES = 200_000;

export type BadgeFile = { kind: string; version?: unknown; settings: Record<string, unknown> };
export type BadgeFileProblem = "too_large" | "not_badge" | "newer";

export function exportBadgeFile(settings: BadgeSettings) {
  return JSON.stringify({ kind: BADGE_FILE_KIND, version: 1, settings }, null, 2);
}

export function readBadgeFile(text: string): { file: BadgeFile } | { problem: BadgeFileProblem } {
  if (new TextEncoder().encode(text).length > MAX_FILE_BYTES) return { problem: "too_large" };
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    return { problem: "not_badge" };
  }
  const file = value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
  const kind = file?.kind;
  const accepted = kind === BADGE_FILE_KIND || (EVENTS_FILE_KINDS as readonly unknown[]).includes(kind);
  const settings = file?.settings;
  if (!file || !accepted || !settings || typeof settings !== "object" || Array.isArray(settings)) return { problem: "not_badge" };
  if (kind === BADGE_FILE_KIND && file.version !== 1) return { problem: "newer" };
  return { file: { kind: kind as string, version: file.version, settings: settings as Record<string, unknown> } };
}

export function downloadBadgeFile(settings: BadgeSettings) {
  const url = URL.createObjectURL(new Blob([exportBadgeFile(settings)], { type: "application/json" }));
  Object.assign(document.createElement("a"), { href: url, download: "badge-design.json" }).click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
