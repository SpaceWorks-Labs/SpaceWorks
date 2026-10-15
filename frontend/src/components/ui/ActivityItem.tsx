import type { ReactNode } from "react";
import { Avatar } from "./Avatar";
import { RelativeTime } from "./RelativeTime";
export type ActivityItemProps = { actor: string; children: ReactNode; object?: string; date: string; seed?: string; exact?: boolean };
export function ActivityItem({ actor, children, object, date, seed, exact }: ActivityItemProps) {
  return <li className="flex min-w-0 gap-3 py-3">
    <Avatar name={actor} seed={seed} size="sm" />
    <div className="min-w-0 text-sm text-ink"><p><strong>{actor}</strong> {children}{object ? <> · <strong>{object}</strong></> : null}</p>
      <p className="mt-1 text-muted"><RelativeTime date={date} exact={exact} /></p></div>
  </li>;
}
