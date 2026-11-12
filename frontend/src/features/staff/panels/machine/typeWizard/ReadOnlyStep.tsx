import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";

import { RouteLink } from "../../../../../components/ui/RouteLink";

/** A step whose values have no endpoint of their own here: the template's values are shown read-only beside a link to the screen that owns them. */
export function ReadOnlyStep({ intro, rows, href, linkLabel, children }: {
  intro: string; rows: [string, string][]; href?: string; linkLabel?: string; children?: ReactNode;
}) {
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{intro}</p>
    {rows.length ? <dl className="grid gap-2 rounded-lg border border-line p-3 text-sm">{rows.map(([label, value]) => <div key={label} className="grid gap-1 sm:grid-cols-[12rem_1fr] sm:gap-3">
      <dt className="text-muted">{label}</dt><dd className="min-w-0 break-words text-ink">{value}</dd></div>)}</dl> : <p className="text-sm text-muted">{t`The template has nothing to suggest here.`}</p>}
    {children}
    {href ? <p><RouteLink href={href} className="desk-button inline-flex min-h-11 items-center">{linkLabel ?? t`Open the screen that owns this`}</RouteLink></p> : null}
  </div>;
}

export const yesNo = (value: boolean | undefined) => value ? t`Yes` : t`No`;
