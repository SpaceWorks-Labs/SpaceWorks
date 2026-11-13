import { t } from "@lingui/core/macro";
import type { Stat } from "./types";
import { ProgressBar } from "./ProgressBar";
import { RouteLink } from "./RouteLink";
import { StatusPill } from "./StatusPill";
export type StatCardProps = Stat;
export function StatCard({ label, value, of, progress, tone = "neutral", href }: StatCardProps) {
  const classes = "block min-h-28 min-w-0 rounded-xl border border-line bg-panel p-4 text-left";
  const content = <>
    <p className="text-sm text-muted">{label}</p>
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <p className="font-display text-heading font-semibold tabular-nums text-ink">{value}
        {of !== undefined ? <span className="ml-1 font-sans text-base font-semibold text-muted">/ {of}</span> : null}</p>
      {tone !== "neutral" ? <StatusPill tone={tone === "attention" ? "emphasis" : tone}
        label={tone === "attention" ? t`Needs attention` : tone === "danger" ? t`Action needed` : t`On track`} /> : null}
    </div>
    {progress !== undefined ? <div className="mt-3"><ProgressBar value={progress} label={`${label} progress`} /></div> : null}
  </>;
  return href ? <RouteLink href={href} className={`${classes} hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus`}>{content}</RouteLink>
    : <div className={classes}>{content}</div>;
}
