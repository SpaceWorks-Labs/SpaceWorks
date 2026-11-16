import { t } from "@lingui/core/macro";
import { RouteLink } from "../../components/ui/RouteLink";
import { MakerspaceSection } from "./MakerspaceSection";

/** Reuse the public header's enabled destinations without loading another domain's listings. */
export function MakerspaceAreas({ links }: { links: { label: string; href: string }[] }) {
  if (!links.length) return null;
  return <MakerspaceSection id="explore" title={t`Explore this space`}>
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {links.map(link => <li key={link.href}><RouteLink href={link.href}
        className="desk-panel flex min-h-14 items-center justify-between gap-3 p-4 font-semibold text-brand-ink hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
        {link.label}<span aria-hidden="true">→</span>
      </RouteLink></li>)}
    </ul>
  </MakerspaceSection>;
}
