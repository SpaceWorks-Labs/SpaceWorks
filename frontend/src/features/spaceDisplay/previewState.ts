import { t } from "@lingui/core/macro";
import type { DisplayConfigInput, DisplayState, HereNow, PersonCard } from "./api";

type Paired = Extract<DisplayState, { state: "paired" }>;

const PEOPLE: PersonCard[] = [
  { handle: "sample-a", display_name: t`Asha Verma`, avatar_url: null, headline: t`Woodworker`, status: { preset: "working", note: t`Cutting a table top` },
    skills: ["CNC", "Joinery"], presence_status: "working", since: "2026-01-01T09:00:00Z" },
  { handle: "sample-b", display_name: t`Tomas Berg`, avatar_url: null, headline: t`Electronics`, status: null,
    skills: ["Soldering"], presence_status: "working", since: "2026-01-01T09:30:00Z" },
];

/** Same narrowing the server applies, so the preview never shows more than the screen will. */
export function previewHereNow(privacy: DisplayConfigInput["privacy"]): HereNow {
  const total = 6;
  if (privacy === "counts") return { audience: "public", people: [], others_count: total, total };
  if (privacy === "first_names") {
    return { audience: "public", total, others_count: total - PEOPLE.length,
      people: PEOPLE.map((p) => ({ ...p, handle: null, display_name: p.display_name.split(" ")[0], headline: "", status: null, skills: [] })) };
  }
  return { audience: "public", people: PEOPLE, others_count: total - PEOPLE.length, total };
}

export function sampleState(input: DisplayConfigInput, spaceName: string): Paired {
  const start = Date.now() + 3_600_000;
  return {
    state: "paired", generated_at: new Date().toISOString(), space: { name: spaceName, slug: "preview", timezone: "UTC" },
    config: { name: input.name ?? "", panels: input.panels ?? [], rotation_seconds: input.rotation_seconds ?? 15, version: 0,
      layout: input.layout ?? "playlist", theme: input.theme ?? "dark", privacy: input.privacy ?? "profiles",
      refresh_seconds: input.refresh_seconds ?? 30, slide_seconds: input.slide_seconds ?? {} },
    here_now: previewHereNow(input.privacy),
    calendar: { month: new Date().toISOString().slice(0, 7), live: [], events: [
      { token: "a", title: t`Open workshop night`, starts_at: new Date(start).toISOString(), ends_at: new Date(start + 7_200_000).toISOString(), location: t`Main floor`, delivery_mode: "in_person", live: false },
      { token: "b", title: t`Laser cutter induction`, starts_at: new Date(start + 86_400_000).toISOString(), ends_at: new Date(start + 93_600_000).toISOString(), location: "", delivery_mode: "in_person", live: false }] },
    machines: { in_use: 2, free: 5, out_of_service: 1, items: [
      { name: t`Laser cutter`, type: t`Laser`, status: "in_use" }, { name: t`Prusa MK4`, type: t`3D printer`, status: "free" }] },
    announcement: input.announcement || t`Welcome. Tidy your bench before you leave.`,
    public_stats: { period: t`This month`, metrics: [
      { key: "printing.jobs", label: t`Prints completed`, value: 42, kind: "count", suppressed: false },
      { key: "machines.hours", label: t`Machine hours`, value: 118, kind: "hours", suppressed: false },
      { key: "events.held", label: t`Events held`, value: 9, kind: "count", suppressed: false }] },
    inventory_highlights: { items: [
      { name: t`Oscilloscope`, category: t`Electronics`, image_url: null, availability: { mode: "exact_count", count: 3, label: t`Available` } },
      { name: t`Soldering station`, category: t`Electronics`, image_url: null, availability: { mode: "status_only", label: t`Limited` } },
      { name: t`Cordless drill`, category: t`Tools`, image_url: null, availability: { mode: "status_only", label: t`Available` } }] },
    sponsors: { sponsors: [{ name: t`Acme Fabrication`, tier: t`Gold`, logo_url: null }, { name: t`Northwind Supplies`, tier: t`Silver`, logo_url: null }] },
    opening_hours: { weekly: Object.fromEntries(["mon", "tue", "wed", "thu", "fri", "sat", "sun"].map((d) => [d, d === "sun" ? [] : [{ start: "10:00", end: "18:00" }]])) },
  };
}
