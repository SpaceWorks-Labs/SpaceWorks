import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";

import { Icon } from "../../../components/ui";
import { RouteLink } from "../../../components/ui/RouteLink";
import { BoxSpinner } from "../../../components/BoxSpinner";

export type RelatedLink = {
  key: string;
  label: string;
  href: string;
  /** A number shows as a count; `null` while it loads; `undefined` when the area has no count. */
  count?: number | null;
  helper?: string;
};

/** A candidate link whose area may be closed to the viewer (`href` undefined); those are dropped. */
export type RelatedCandidate = Omit<RelatedLink, "href"> & { href?: string };
export function openLinks(candidates: RelatedCandidate[]): RelatedLink[] {
  return candidates.filter((row): row is RelatedLink => Boolean(row.href));
}

/**
 * "Related" cross-links: one row per area the viewer can open, each a real link to that area's
 * own list with the record pre-selected. Rows for areas the viewer does not manage are never
 * passed in (decision 224), so nothing here re-checks authority.
 */
export function RelatedLinks({ title = t`Related`, links, empty, children }: {
  title?: string; links: RelatedLink[]; empty?: string; children?: ReactNode;
}) {
  return <section className="grid min-w-0 gap-3" aria-label={title}>
    <h3 className="title-section">{title}</h3>
    {links.length ? <ul className="grid min-w-0 gap-2 sm:grid-cols-2">
      {links.map(link => <li key={link.key} className="min-w-0">
        <RouteLink href={link.href} className="flex min-h-11 min-w-0 items-center justify-between gap-3 rounded-control border border-line bg-panel px-3 py-2 hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
          <span className="grid min-w-0">
            <span className="font-semibold [overflow-wrap:anywhere]">{link.label}</span>
            {link.helper ? <span className="text-sm text-muted [overflow-wrap:anywhere]">{link.helper}</span> : null}
          </span>
          <span className="flex shrink-0 items-center gap-2 text-sm text-muted">
            {link.count === null ? <BoxSpinner label={t`Loading count`} size={16} />
              : typeof link.count === "number" ? <span className="rounded-full bg-surface px-2 py-0.5 font-semibold text-ink">{link.count}</span> : null}
            <Icon name="ArrowRight" className="h-4 w-4" />
          </span>
        </RouteLink>
      </li>)}
    </ul> : <p className="text-sm text-muted">{empty ?? t`Nothing linked to this yet.`}</p>}
    {children}
  </section>;
}
