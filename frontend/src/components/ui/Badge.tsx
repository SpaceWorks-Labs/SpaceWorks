import type { PropsWithChildren } from "react";

// Status colour always accompanies a word; label inks stay readable in both modes.
type BadgeTone = "success" | "warn" | "danger" | "accent" | "emphasis" | "info" | "neutral";

type BadgeProps = PropsWithChildren<{
  tone: BadgeTone;
}>;

const toneClasses: Record<BadgeTone, string> = {
  success: "border-transparent bg-success text-on-success dark:bg-success-soft dark:text-success-ink",
  warn: "border-transparent bg-warn text-on-warn dark:bg-warn-soft dark:text-warn-ink",
  danger: "border-danger-line bg-panel text-danger",
  accent: "border-transparent bg-accent-soft text-accent-ink",
  info: "border-transparent bg-info text-on-info dark:bg-info-soft dark:text-info-ink",
  emphasis: "border-emphasis bg-emphasis text-on-emphasis",
  neutral: "border-line bg-surface text-ink",
};

export function Badge({ tone, children }: BadgeProps) {
  return (
    <span
      className={`inline-flex min-h-6 items-center rounded-full border px-2 py-0.5 text-xs font-medium tracking-tight ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}
