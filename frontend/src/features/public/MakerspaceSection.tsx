import type { ReactNode } from "react";
import { ArrowRight } from "lucide-react";
import { RouteLink } from "../../components/ui/RouteLink";

type Props = { id: string; title: string; subtitle?: string; more?: { label: string; href: string }; children: ReactNode };

/** One titled band of the makerspace page; `more` links to that section's full page. */
export function MakerspaceSection({ id, title, subtitle, more, children }: Props) {
  const headingId = `${id}-title`;
  return <section id={id} aria-labelledby={headingId} data-section={id} className="mb-12 min-w-0 scroll-mt-6">
    <div className="mb-4 flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
      <div className="min-w-0">
        <h2 id={headingId} className="title-page">{title}</h2>
        {subtitle ? <p className="mt-1 text-sm text-muted">{subtitle}</p> : null}
      </div>
      {more ? <RouteLink href={more.href} className="inline-flex min-h-11 items-center gap-1 rounded-control text-sm font-semibold text-brand-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
        {more.label}<ArrowRight aria-hidden="true" size={16} />
      </RouteLink> : null}
    </div>
    {children}
  </section>;
}
