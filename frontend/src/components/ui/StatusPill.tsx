import type { ReactNode } from "react";
import { Icon, type IconName } from "./icon";
import { toneMarkClasses } from "./tones";
import type { Tone } from "./types";
export type StatusPillProps = { label: string; tone?: Tone; icon?: IconName; children?: ReactNode };
const toneIcons: Record<Tone, IconName> = { success: "CheckCircle", warn: "Clock", danger: "CircleAlert",
  accent: "Circle", emphasis: "TriangleAlert", info: "Info", neutral: "Circle" };
export function StatusPill({ label, tone = "neutral", icon, children }: StatusPillProps) {
  return <span className={`inline-flex min-h-6 max-w-full items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${toneMarkClasses[tone]}`}>
    <Icon name={icon ?? toneIcons[tone]} className="h-3 w-3" />{children || label.trim() || "Unknown"}
  </span>;
}
