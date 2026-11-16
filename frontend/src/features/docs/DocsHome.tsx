import { t } from "@lingui/core/macro";
import { ArrowRight, BookOpen, Boxes, Server, SquareTerminal } from "lucide-react";
import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { PageMetadata } from "../../components/PageMetadata";
import { API_REFERENCE_PATH, DOCS_VERSION, docGroups, groupAnchor, groupLabel } from "./docsIndex";
import type { DocEntry } from "./docsTypes";

function groupBlurb(group: string) {
  const blurbs: Record<string, string> = {
    "Getting started": t`What Space Works is, the words it uses and your first hour with it.`,
    Tutorials: t`Step-by-step lessons that end with something working.`,
    "User guides": t`What each role does day to day: members, front desk, managers and organisers.`,
    "How-to guides": t`Short recipes for one task each.`,
    "Areas & modules": t`Every area a space can switch on, what it adds and what happens when it is off.`,
    Architecture: t`How the system is put together: requests, tenancy, roles, data and integrations.`,
    Hosting: t`Every way to install, update, back up, monitor and secure a server.`,
    API: t`The REST API, its reference, signed clients, webhooks and devices.`,
    Reference: t`Settings, environment variables, audit actions and other lookup tables.`,
    Project: t`Licences, security policy, contributing and how releases are made.`,
    Changelog: t`What changed in each release and how to upgrade.`,
  };
  return blurbs[group] ?? "";
}

/** The docs front door: four ways in, then every group with its pages and summaries. */
export function DocsHome({ source, onSearch }: { source?: readonly DocEntry[]; onSearch: () => void }) {
  const groups = docGroups(source);
  const { hash } = useLocation();
  useEffect(() => {
    const target = hash ? document.getElementById(hash.slice(1)) : null;
    if (target) target.scrollIntoView({ block: "start" }); else window.scrollTo({ top: 0 });
  }, [hash]);
  const doors = [
    { icon: BookOpen, title: t`Get started`, body: t`Install, set up a space and run your first handover.`, to: `#${groupAnchor("Getting started")}` },
    { icon: Server, title: t`Host it`, body: t`One-line install, hybrid setups, cloud recipes and backups.`, to: `#${groupAnchor("Hosting")}` },
    { icon: Boxes, title: t`Areas and modules`, body: t`Inventory, machines, events, bookings, shop and money.`, to: `#${groupAnchor("Areas & modules")}` },
    { icon: SquareTerminal, title: t`API reference`, body: t`Every endpoint, grouped by area, with a curl example.`, to: API_REFERENCE_PATH },
  ];
  return <div className="sw-doc-home">
    <PageMetadata title={t`Documentation · Space Works`} path="/docs" siteName="Space Works"
      description={t`Install, run and extend Space Works: guides for every role, every area and module, hosting, the architecture and the API reference.`} />
    <header className="grid gap-5 pb-10">
      <span className="sw-doc-version w-fit">{t`Version ${DOCS_VERSION}`}</span>
      <h1 className="sw-hub-h2">{t`Space Works documentation`}</h1>
      <p className="sw-hub-lede">{t`How to install it, run a space with it and build on it. Written for organisers, staff, members and the people who keep the server running.`}</p>
      <button type="button" className="sw-doc-search-hero" onClick={onSearch}>
        <span>{t`Search pages, sections and API endpoints…`}</span><kbd className="sw-doc-kbd">{t`Ctrl K`}</kbd></button>
    </header>
    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {doors.map(({ icon: Icon, title, body, to }) => <li key={title}>
        <Link to={to} className="sw-doc-door"><Icon size={22} aria-hidden="true" className="text-accent-ink" />
          <span className="flex items-center gap-2 font-extrabold text-ink">{title}<ArrowRight size={16} aria-hidden="true" /></span>
          <span className="text-sm text-muted">{body}</span></Link>
      </li>)}
    </ul>
    {groups.map(group => <section key={group.name} id={groupAnchor(group.name)} aria-labelledby={`${groupAnchor(group.name)}-title`} className="sw-doc-group">
      <div className="grid gap-2">
        <h2 id={`${groupAnchor(group.name)}-title`} className="text-2xl font-extrabold text-ink">{groupLabel(group.name)}</h2>
        {groupBlurb(group.name) ? <p className="text-muted">{groupBlurb(group.name)}</p> : null}
      </div>
      <ul className="sw-doc-group-list">
        {group.name === "API" ? <li><Link to={API_REFERENCE_PATH} className="sw-doc-group-link">
          <span className="font-semibold text-ink">{t`API reference`}</span>
          <span className="text-sm text-muted">{t`Every endpoint, generated from the OpenAPI schema.`}</span></Link></li> : null}
        {group.pages.map(page => <li key={page.id}><Link to={`/docs/${page.id}`} className="sw-doc-group-link">
          <span className="font-semibold text-ink">{page.title}</span>
          {page.summary ? <span className="line-clamp-2 text-sm text-muted">{page.summary}</span> : null}</Link></li>)}
      </ul>
    </section>)}
  </div>;
}
