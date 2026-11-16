import { t } from "@lingui/core/macro";
import { ArrowRight, ArrowUpRight, FileText, FolderGit2, GitPullRequest, History, Scale, ShieldAlert, Type } from "lucide-react";
import { Link } from "react-router-dom";
import { ExternalLink } from "../ExternalLink";
import { ANDROID_REPO_URL, DOCS_LINKS, GITHUB_URL, IOS_REPO_URL, LICENSE_SPDX, LICENSE_URL } from "../hubLinks";

/** The AGPL in plain words, row for row from docs/project/license.md (the licence text still wins). */
function terms() {
  return [
    { who: t`Running it as released`, what: t`Nothing extra. Use it for your space, your organisation or as a service for others, commercial or not.` },
    { who: t`Changing it for yourself`, what: t`Read every line and change anything. If only you use your changed version, there is nothing to publish.` },
    { who: t`Running a changed version for others`, what: t`Offer the people who use it over the network the source of your changes, under the same licence.` },
  ];
}

function projectLinks() {
  return [
    { icon: Scale, label: t`The licence, in plain words`, to: DOCS_LINKS.license },
    { icon: Type, label: t`Third-party software and font licences`, to: DOCS_LINKS.thirdParty },
    { icon: ShieldAlert, label: t`Security policy`, to: DOCS_LINKS.securityPolicy },
    { icon: GitPullRequest, label: t`Contributing`, to: DOCS_LINKS.contributing },
    { icon: History, label: t`Changelog and release notes`, to: DOCS_LINKS.changelog },
  ];
}

/** The three official repositories, each named by what it holds. */
function repositories() {
  return [
    { name: t`Space Works: server, web app and docs`, href: GITHUB_URL },
    { name: t`Android app`, href: ANDROID_REPO_URL },
    { name: t`iOS app`, href: IOS_REPO_URL },
  ].map(repo => ({ ...repo, slug: new URL(repo.href).pathname.slice(1) }));
}

/** What the licence lets you do, and where the project's rules live: in the docs and on GitHub. */
export function OpenSourceSection() {
  return <section id="open-source" aria-labelledby="open-source-title" className="sw-hub-section">
    <div className="sw-hub-wrap">
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:items-end md:gap-10">
        <h2 id="open-source-title" className="sw-hub-h2">{t`Open source, in plain words.`}</h2>
        <p className="sw-hub-lede">{t`Space Works is free software under the GNU Affero General Public License, version 3 or any later version. No licence fee, no per-space permission to ask, and no contributor licence agreement.`}</p>
      </div>
      <div className="mt-10 grid gap-6 lg:mt-14 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-10">
        <div className="sw-hub-licence">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4 md:px-6">
            <p className="flex items-center gap-2 font-semibold text-ink"><FileText size={18} aria-hidden="true" />{t`What the licence asks of you`}</p>
            <span className="sw-hub-spdx code-text">{LICENSE_SPDX}</span>
          </div>
          <dl>
            {terms().map(term => <div key={term.who} className="sw-hub-licence-row">
              <dt className="font-extrabold text-ink">{term.who}</dt>
              <dd className="leading-7 text-muted">{term.what}</dd>
            </div>)}
          </dl>
          <p className="border-t border-line bg-surface px-5 py-3 text-sm text-muted md:px-6">
            {t`A summary, not legal advice: the LICENSE file is the governing text.`}</p>
        </div>
        <nav aria-labelledby="open-source-links-title" className="grid content-start gap-4">
          <h3 id="open-source-links-title" className="title-section">{t`Licence and project pages`}</h3>
          <ul className="grid border-t border-line">
            {projectLinks().map(({ icon: Icon, label, to }) => <li key={to} className="border-b border-line">
              <Link to={to} className="sw-hub-row-link"><Icon size={20} aria-hidden="true" className="shrink-0 text-accent-ink" />
                <span className="min-w-0 flex-1">{label}</span><ArrowRight size={16} aria-hidden="true" className="shrink-0" /></Link>
            </li>)}
          </ul>
          <h3 id="open-source-repos-title" className="title-section pt-4">{t`Official repositories`}</h3>
          <ul aria-labelledby="open-source-repos-title" className="grid border-t border-line">
            {repositories().map(({ name, href, slug }) => <li key={href} className="border-b border-line">
              <ExternalLink href={href} label={t`${name}, ${slug}, on GitHub (opens in a new tab)`} className="sw-hub-row-link">
                <FolderGit2 size={20} aria-hidden="true" className="shrink-0 text-accent-ink" />
                <span className="grid min-w-0 flex-1"><span>{name}</span><span className="code-text truncate text-sm font-normal text-muted">{slug}</span></span>
              </ExternalLink>
            </li>)}
          </ul>
          <div className="flex flex-wrap gap-3 pt-2">
            <a href={GITHUB_URL} target="_blank" rel="noreferrer noopener" className="desk-button-primary gap-2">{t`Source on GitHub`}
              <ArrowUpRight size={16} aria-hidden="true" /><span className="sr-only">{t`(opens in a new tab)`}</span></a>
            <a href={LICENSE_URL} target="_blank" rel="noreferrer noopener" className="desk-button gap-2">{t`LICENSE file`}
              <ArrowUpRight size={16} aria-hidden="true" /><span className="sr-only">{t`(opens in a new tab)`}</span></a>
          </div>
        </nav>
      </div>
    </div>
  </section>;
}
