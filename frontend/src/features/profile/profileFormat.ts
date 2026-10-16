import {
  AtSign, Bot, BrainCircuit, Code, Cpu, FolderGit2, Globe, Hash, HeartHandshake, Link2, Palette, Printer,
  Sparkles, Wrench, type LucideIcon,
} from "lucide-react";

const day = (value: Date) => value.toLocaleDateString(undefined, { day: "numeric", month: "short" });
const time = (value: Date) => value.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });

/** "9 Sep · 8:00 PM – 9:30 PM", or both dates when the event runs past midnight. */
export function eventRange(startsAt: string, endsAt: string) {
  const start = new Date(startsAt);
  const end = new Date(endsAt);
  if (Number.isNaN(start.getTime())) return "";
  if (Number.isNaN(end.getTime())) return `${day(start)} · ${time(start)}`;
  return start.toDateString() === end.toDateString()
    ? `${day(start)} · ${time(start)} – ${time(end)}`
    : `${day(start)} · ${time(start)} – ${day(end)} · ${time(end)}`;
}

const monthYear = (value: string) => {
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(undefined, { month: "short", year: "numeric" });
};

/** Timeline dates are calendar dates (no time zone); an open end reads "Present". */
export function timelineRange(start: string, end: string | null) {
  return `${monthYear(start)} – ${end ? monthYear(end) : "Present"}`;
}

/** Brand marks are not in the icon set, so links get a generic glyph and always carry a text label. */
export function linkPresentation(link: { kind: string; url: string }): { label: string; Icon: LucideIcon } {
  let host = "";
  try { host = new URL(link.url).hostname.replace(/^www\./, ""); } catch { host = ""; }
  const kind = link.kind.trim();
  const key = `${kind} ${host}`.toLowerCase();
  const Icon = /github|gitlab|codeberg/.test(key) ? FolderGit2
    : /twitter|x\.com|\bx\b|mastodon|bsky|threads|instagram|linkedin/.test(key) ? AtSign
      : /site|web|portfolio|blog/.test(key) ? Globe : Link2;
  return { label: kind || host || "Link", Icon };
}

const DOMAIN_ICONS: [RegExp, LucideIcon][] = [
  [/\bai\b|artificial/i, Sparkles], [/machine learning|\bml\b|data/i, BrainCircuit], [/robot/i, Bot],
  [/volunteer|community/i, HeartHandshake], [/web|software|code|program|app/i, Code],
  [/electronic|embedded|hardware|iot|fpga/i, Cpu], [/3d|print|fabricat/i, Printer],
  [/design|art|craft/i, Palette], [/wood|metal|mechanic|cnc/i, Wrench],
];

export function domainIcon(domain: string): LucideIcon {
  return DOMAIN_ICONS.find(([pattern]) => pattern.test(domain))?.[1] ?? Hash;
}

export const SKILL_LEVELS = ["Familiar", "Comfortable", "Fluent"] as const;
export const skillLevelLabel = (level: number) => SKILL_LEVELS[Math.min(Math.max(level, 1), 3) - 1];
