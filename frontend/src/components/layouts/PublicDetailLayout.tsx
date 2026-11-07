import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ActionControl, IdentityChip, PageHeader, StatusPill, Tabs } from "../ui";
import type { Identity, StatusPillProps } from "../ui";
import { LayoutFrame, QueryContent, useLayoutQuery } from "./LayoutFrame";
import { PublicActionCard, type PublicActionCardProps } from "./PublicActionCard";
import type { ContentSection, LayoutProps } from "./types";

export type PublicDetailLayoutProps = LayoutProps & {
  cover?: { src: string; alt: string };
  chips?: StatusPillProps[];
  title: string;
  tagline?: string;
  facts?: { identity: Identity; primary: string; secondary?: string }[];
  sections: ContentSection[];
  actionCard: PublicActionCardProps;
  host?: { identity: Identity; name: string; href: string };
};
export function PublicDetailLayout({ cover, chips = [], title, tagline, facts = [], sections, actionCard, host,
  standalone = false, width, ...query }: PublicDetailLayoutProps) {
  const resolved = useLayoutQuery(query);
  const [active, setActive] = useState(sections[0]?.id ?? "");
  return <LayoutFrame standalone={standalone} width={width} className="sw-public-detail">
    {cover ? <img src={cover.src} alt={cover.alt} className="mb-8 aspect-[3.5] w-full rounded-xl object-cover" /> : null}
    <div className="sw-public-columns">
      <div className="min-w-0">
        <div className="mb-4 flex min-w-0 gap-2 overflow-x-auto">{chips.map(chip => <StatusPill key={chip.label} {...chip} />)}</div>
        <PageHeader title={title} />
        {tagline ? <p className="mb-8 break-words font-accent text-xl text-brand-ink md:text-2xl">{tagline}</p> : null}
        <QueryContent {...resolved}>
          {facts.length ? <div className="mb-8 flex flex-wrap gap-6">{facts.map(fact => <div key={fact.primary} className="flex min-w-0 items-center gap-3">
            <IdentityChip identity={fact.identity} label={fact.primary} /><div className="min-w-0"><p className="font-semibold">{fact.primary}</p>
              {fact.secondary ? <p className="text-sm text-muted">{fact.secondary}</p> : null}</div>
          </div>)}</div> : null}
          {sections.length ? <div className="mb-8" onClick={event => {
            const anchor = (event.target as HTMLElement).closest("a"); if (anchor?.hash) setActive(anchor.hash.slice(1));
          }}><Tabs label={t`Page sections`} tabs={sections.map(section => ({ key: section.id, label: section.label, href: `#${section.id}` }))} activeKey={active} /></div> : null}
          <div className="grid gap-10">{sections.map(section => <section key={section.id} id={section.id} aria-label={section.label}
            tabIndex={-1} className="min-w-0 scroll-mt-6 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
            <h2 className="title-panel mb-4">{section.label}</h2>{section.content}
          </section>)}</div>
          {host ? <div className="mt-10 flex items-center gap-3 border-t border-line pt-6">
            <IdentityChip identity={host.identity} label={host.name} /><div><p className="text-sm text-muted">{t`Hosted by`}</p>
              <ActionControl action={{ label: host.name, href: host.href }} /></div>
          </div> : null}
        </QueryContent>
      </div>
      {resolved.state.status === "ready" && !resolved.isEmpty ? <PublicActionCard {...actionCard} /> : null}
    </div>
  </LayoutFrame>;
}
