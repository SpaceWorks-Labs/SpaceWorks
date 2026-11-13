import type { ReactNode } from "react";
import { RouteLink } from "./RouteLink";
import { IdentityChip } from "./IdentityChip";
import type { Identity } from "./types";
export type ListRowProps = { title: string; identity?: Identity; identityContent?: ReactNode; meta?: ReactNode; right?: ReactNode;
  draft?: boolean; href?: string; onClick?: () => void };
export function ListRow({ title, identity, identityContent, meta, right, draft, href, onClick }: ListRowProps) {
  const interactive = Boolean(href || onClick);
  const classes = `relative flex min-h-20 w-full min-w-0 flex-wrap items-center gap-4 rounded-2xl border border-line p-4 text-left ${draft ? "border-dashed bg-surface" : "bg-panel"} ${interactive ? "transition-colors duration-[var(--sw-dur-fast)] hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" : ""}`;
  // The right slot is a sibling of the main row link/button, so inline actions never nest controls.
  const body = <>{identityContent ?? (identity ? <IdentityChip identity={identity} label={title} draft={draft} /> : null)}<span className="min-w-0 flex-1">
    <span className="title-section block break-words">{title}</span>
    {meta ? <span className="mt-1 block text-sm text-muted [overflow-wrap:anywhere]">{meta}</span> : null}</span></>;
  return <div className={classes}>
    {href ? <RouteLink className="flex min-h-11 min-w-0 flex-1 basis-48 items-center gap-4 rounded-control after:absolute after:inset-0 after:rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" href={href}>{body}</RouteLink>
      : onClick ? <button className="flex min-h-11 min-w-0 flex-1 basis-48 items-center gap-4 rounded-control text-left after:absolute after:inset-0 after:rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" type="button" onClick={onClick}>{body}</button>
      : <div className="flex min-w-0 flex-1 basis-48 items-center gap-4">{body}</div>}
    {right ? <div className="relative z-10 min-w-0 max-w-full shrink-0">{right}</div> : null}
  </div>;
}
