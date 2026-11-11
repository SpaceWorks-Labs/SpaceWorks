import { t } from "@lingui/core/macro";
import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { SpaceWorksLogo } from "../../components/SpaceWorksLogo";
import { useOrganizationDirectoryEnabled } from "../organizations/publicDirectoryApi";
import { useHostingConfig } from "../hosting/hostingApi";
import { DOCS_LINKS, GITHUB_URL, HUB_VERSION, ISSUES_URL, LICENSE_SPDX, LICENSE_URL } from "./hubLinks";

type FooterLink = { label: string; to: string; external?: boolean };

function columns(directory: boolean, hosting: boolean): { title: string; links: FooterLink[] }[] {
  return [
    { title: t`Use it`, links: [
      { label: t`Find a space`, to: "/spaces" },
      ...(directory ? [{ label: t`Organizations`, to: "/organizations" }] : []),
      // Decision 295: only while this deployment takes requests for new spaces.
      ...(hosting ? [{ label: t`Request a workspace`, to: "/hosting" }] : []),
      { label: t`Sign in`, to: "/member" },
      { label: t`Staff console`, to: "/admin" }, { label: t`About`, to: "/about" },
    ] },
    { title: t`Docs`, links: [
      { label: t`Getting started`, to: DOCS_LINKS.gettingStarted }, { label: t`Tutorials`, to: DOCS_LINKS.tutorials },
      { label: t`Install and update`, to: DOCS_LINKS.install }, { label: t`Areas and modules`, to: DOCS_LINKS.areas },
      { label: t`API reference`, to: DOCS_LINKS.apiReference }, { label: t`All documentation`, to: DOCS_LINKS.home },
    ] },
    { title: t`Project`, links: [
      { label: t`Licence`, to: DOCS_LINKS.license }, { label: t`Third-party and fonts`, to: DOCS_LINKS.thirdParty },
      { label: t`Security policy`, to: DOCS_LINKS.securityPolicy }, { label: t`Contributing`, to: DOCS_LINKS.contributing },
      { label: t`Changelog`, to: DOCS_LINKS.changelog },
      // Parity A13: this installation's own privacy and terms pages.
      { label: t`Privacy`, to: "/privacy" }, { label: t`Terms`, to: "/terms" },
    ] },
    { title: t`GitHub`, links: [
      { label: t`Source code`, to: GITHUB_URL, external: true }, { label: t`LICENSE file`, to: LICENSE_URL, external: true },
      { label: t`Report a problem`, to: ISSUES_URL, external: true },
    ] },
  ];
}

export function HubFooter() {
  const year = new Date().getFullYear();
  const directory = useOrganizationDirectoryEnabled();
  const hosting = useHostingConfig().data === true;
  return <footer className="sw-hub-footer">
    <div className="sw-hub-wrap grid grid-cols-2 gap-x-6 gap-y-10 py-12 md:grid-cols-4 md:py-16 lg:grid-cols-[minmax(0,1.3fr)_repeat(4,minmax(0,1fr))]">
      <div className="col-span-2 grid content-start gap-4 md:col-span-4 lg:col-span-1">
        <Link to="/" aria-label={t`Space Works home`} className="w-fit rounded-control focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-focus">
          <SpaceWorksLogo variant="stacked" size={180} decorative />
        </Link>
        <p className="max-w-xs text-sm leading-6 text-muted">{t`Open-source software for makerspaces, fab labs and community workshops.`}</p>
      </div>
      {columns(directory, hosting).map(column => <nav key={column.title} aria-label={t`Footer: ${column.title}`} className="grid content-start gap-1">
        <h2 className="title-section mb-2">{column.title}</h2>
        {column.links.map(link => link.external
          ? <a key={link.label} href={link.to} target="_blank" rel="noreferrer noopener" className="sw-hub-footer-link">
            {link.label}<ArrowUpRight size={14} aria-hidden="true" /><span className="sr-only">{t`(opens in a new tab)`}</span></a>
          : <Link key={link.label} to={link.to} className="sw-hub-footer-link">{link.label}</Link>)}
      </nav>)}
    </div>
    <div className="border-t border-line">
      <div className="sw-hub-wrap flex flex-wrap items-center justify-between gap-3 py-5 text-sm text-muted">
        <p>{t`© ${year} Space Works contributors. Free software under ${LICENSE_SPDX}.`}</p>
        <Link to={DOCS_LINKS.changelog} className="sw-hub-footer-link code-text">{t`Version ${HUB_VERSION}`}</Link>
      </div>
    </div>
  </footer>;
}
