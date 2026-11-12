import { t } from "@lingui/core/macro";
import { ArrowRight, BookOpen, Boxes, Braces, GraduationCap, Network, Search, Server, Smartphone, Tablet, TabletSmartphone } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PatchMoment } from "../../../components/delight/PatchMoment";
import { ExternalLink } from "../ExternalLink";
import { ANDROID_RELEASES_URL, DOCS_LINKS, IOS_RELEASES_URL } from "../hubLinks";

/** Where people use it today: the browser, the installable member area, kiosks, and the released native apps (source public on GitHub). */
export function AppsSection() {
  const rows = [
    { icon: TabletSmartphone, title: t`Web app on any phone`, body: t`Members and staff use Space Works in the browser on any phone, tablet or computer. Nothing to download.`, ready: true },
    { icon: Smartphone, title: t`Installable member area`, body: t`Members can add their member area to the home screen and keep their member card readable offline.`, ready: true },
    { icon: Tablet, title: t`Kiosk stations`, body: t`A scanner station at the desk keeps recording handovers through a dropped connection and catches up when it is back.`, ready: true },
    { icon: Smartphone, title: t`Android app`, body: t`The native Android app for members and staff.`, ready: true,
      repo: { href: ANDROID_RELEASES_URL, label: t`Download from GitHub Releases: the latest Android app (opens in a new tab)` } },
    { icon: Smartphone, title: t`iPhone and iPad app`, body: t`The native iPhone and iPad app for members and staff.`, ready: true,
      repo: { href: IOS_RELEASES_URL, label: t`Download from GitHub Releases: the latest iOS app (opens in a new tab)` } },
  ];
  return <section id="apps" aria-labelledby="apps-title" className="sw-hub-section sw-hub-band">
    <div className="sw-hub-wrap grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-16">
      <div className="grid content-start gap-5">
        <h2 id="apps-title" className="sw-hub-h2">{t`On every phone, in the browser and in native apps.`}</h2>
        <p className="sw-hub-lede">{t`Everything works in the browser, and the native Android and iOS apps are released on GitHub, built on the same API.`}</p>
        {/* Patch is this section's one bold moment (brand rules): no symbol pattern here, nothing orange beside it. */}
        <PatchMoment className="mt-2" />
      </div>
      <ul className="grid">
        {rows.map(({ icon: Icon, title, body, ready, repo }) => <li key={title} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-4 border-t border-line py-5 last:border-b">
          <span className="sw-hub-area-icon" aria-hidden="true"><Icon size={20} /></span>
          <div className="min-w-0"><h3 className="text-lg font-extrabold text-ink">{title}</h3><p className="mt-1 text-muted">{body}</p>
            {repo ? <ExternalLink href={repo.href} label={repo.label} className="sw-hub-inline-link mt-2 inline-flex w-fit items-center gap-1">
              {t`Download from GitHub Releases`}</ExternalLink> : null}</div>
          <span className={`inline-flex min-h-7 items-center whitespace-nowrap rounded-full px-3 text-xs font-semibold ${ready ? "bg-success text-on-success" : "bg-warn text-on-warn"}`}>
            {ready ? t`Available` : t`Coming soon`}</span>
        </li>)}
      </ul>
    </div>
  </section>;
}

/** The docs entry on a Citron field: search straight into /docs, or start from one of six doors. */
export function DocsSection() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const doors = [
    { icon: BookOpen, title: t`Getting started`, body: t`From a fresh install to your first tracked loan.`, to: DOCS_LINKS.gettingStarted },
    { icon: GraduationCap, title: t`Tutorials`, body: t`Step by step: first space, first loan, first event, bookings, payments.`, to: DOCS_LINKS.tutorials },
    { icon: Server, title: t`Hosting`, body: t`Every way to install, update, back up and secure it.`, to: DOCS_LINKS.hostingGroup },
    { icon: Boxes, title: t`Areas and modules`, body: t`What each area adds, and what happens when it is off.`, to: DOCS_LINKS.areas },
    { icon: Braces, title: t`API reference`, body: t`Every endpoint, grouped by area, with schemas and curl examples.`, to: DOCS_LINKS.apiReference },
    { icon: Network, title: t`Architecture`, body: t`How requests, tenancy, roles and data fit together.`, to: DOCS_LINKS.architecture },
  ];
  return <section id="docs" aria-labelledby="docs-title" className="sw-hub-wrap">
    <div className="sw-field-citron sw-hub-docs">
      <div className="grid content-start gap-5">
        <h2 id="docs-title" className="sw-hub-h2">{t`Everything is written down.`}</h2>
        <p className="sw-hub-lede">{t`Guides, tutorials, every area and module, hosting, the architecture and the full API reference, published inside this app and versioned with it.`}</p>
        <form role="search" className="flex flex-wrap gap-2" onSubmit={event => { event.preventDefault(); navigate(query.trim() ? DOCS_LINKS.search(query.trim()) : DOCS_LINKS.home); }}>
          <label htmlFor="hub-docs-search" className="sr-only">{t`Search the documentation`}</label>
          <div className="relative min-w-0 flex-1 basis-60">
            <Search size={18} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden="true" />
            <input id="hub-docs-search" type="search" value={query} onChange={event => setQuery(event.target.value)}
              placeholder={t`Try “backup”, “Stripe” or “kiosk”`} className="desk-input min-h-12 w-full pl-10" />
          </div>
          <button type="submit" className="desk-button-primary min-h-12 px-5">{t`Search docs`}</button>
        </form>
        <Link to={DOCS_LINKS.home} className="sw-hub-inline-link w-fit">{t`Browse all documentation`}</Link>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2">
        {doors.map(({ icon: Icon, title, body, to }) => <li key={title}>
          <Link to={to} className="sw-hub-door"><Icon size={22} aria-hidden="true" className="mt-0.5 shrink-0" />
            <span className="grid gap-1"><span className="flex items-center gap-2 font-extrabold text-ink">{title}<ArrowRight size={16} aria-hidden="true" /></span>
              <span className="text-sm text-muted">{body}</span></span></Link>
        </li>)}
      </ul>
    </div>
  </section>;
}
