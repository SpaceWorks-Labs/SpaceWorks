import { t } from "@lingui/core/macro";
import { useId, type ReactNode } from "react";
import { RouteLink } from "./RouteLink";
export type ActivityRailProps = { children: ReactNode; title?: string; href?: string };
export function ActivityRail({ children, title = t`Recent activity`, href }: ActivityRailProps) {
  const id = useId();
  return <aside aria-labelledby={id} className="min-w-0">
    <h2 id={id} className="title-panel">{title}</h2>
    <ul className="mt-3">{children}</ul>
    {href ? <RouteLink href={href} className="desk-button-ghost mt-3 underline">{t`See all activity →`}</RouteLink> : null}
  </aside>;
}
