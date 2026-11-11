import { plural, t } from "@lingui/core/macro";
import { useId, useMemo, useState } from "react";
import { PublicLayout, type PublicLayoutProps } from "../../components/layouts";
import { ListRow } from "../../components/ui";
import { RouteLink } from "../../components/ui/RouteLink";
import { HELP_SECTIONS, SECTION_BY_ID } from "./helpSections";
import { searchHelp } from "./helpSearch";
import type { HelpArticle } from "./helpTypes";

export type HelpChrome = Pick<PublicLayoutProps, "makerspace" | "nav" | "headerAction" | "liveStatus" | "width" | "footer">;

const LINK = "rounded-control text-accent-ink underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

function SignInNote({ memberHref }: { memberHref: string }) {
  return <p className="rounded-2xl border border-line bg-surface p-4 text-sm text-muted">
    {t`Guides for staff roles appear here once you `}<RouteLink className={`${LINK} font-semibold underline`} href={memberHref}>{t`sign in`}</RouteLink> {t` with an account that holds one.`}</p>;
}

type Props = { chrome: HelpChrome; articles: HelpArticle[]; sectionId: string; loading: boolean; signedIn: boolean;
  memberHref: string; hrefFor: (target: string) => string; spaceName: string | null };

/** The guide's front page (sections and search) or one section's article list. */
export function HelpIndex({ chrome, articles, sectionId, loading, signedIn, memberHref, hrefFor, spaceName }: Props) {
  const [query, setQuery] = useState("");
  const searchId = useId();
  const results = useMemo(() => searchHelp(articles, query), [articles, query]);
  const section = sectionId ? SECTION_BY_ID.get(sectionId) : undefined;
  const sections = HELP_SECTIONS.filter(item => (!sectionId || item.id === sectionId) && articles.some(article => article.section === item.id));
  const header = section
    ? { eyebrow: t`Help`, title: section.title, subtitle: section.summary }
    : { eyebrow: spaceName ? t`${spaceName} · Help` : t`Help`, title: t`How can we help?`, subtitle: t`Step-by-step guides for what you can do here.` };
  const searching = query.trim().length > 0;
  const empty = Boolean(sectionId) && !loading && sections.length === 0;

  return <PublicLayout {...chrome} header={header} state={{ status: loading ? "loading" : "ready" }}
    breadcrumb={section ? [{ label: t`Help`, href: hrefFor("") }, { label: section.title }] : undefined}
    isEmpty={empty} empty={{ message: t`There are no articles here for you. Sign in with the right account, or go back to the help front page.` }}>
    <div className="grid gap-8">
      <div role="search" className="grid gap-2">
        <label htmlFor={searchId} className="text-sm font-semibold text-ink">{t`Search the guide`}</label>
        <input id={searchId} type="search" className="desk-input w-full" value={query} autoComplete="off"
          placeholder={t`Try “return a tool” or “refund”`} onChange={event => setQuery(event.target.value)} />
        <p className="text-sm text-muted" aria-live="polite">{searching ? plural(results.length, { one: "# article matches", other: "# articles match" }) : ""}</p>
      </div>
      {searching ? <ul className="grid gap-3" aria-label={t`Search results`}>
        {results.map(article => <li key={article.id}>
          <ListRow title={article.title} href={hrefFor(article.id)} meta={`${SECTION_BY_ID.get(article.section)?.title ?? ""} · ${article.summary}`} />
        </li>)}
      </ul> : section ? <ul className="grid gap-3">
        {articles.filter(article => article.section === section.id).map(article => <li key={article.id}>
          <ListRow title={article.title} meta={article.summary} href={hrefFor(article.id)} right={<span aria-hidden="true">→</span>} />
        </li>)}
      </ul> : <div className="grid gap-4 md:grid-cols-2">
        {sections.map(item => {
          const own = articles.filter(article => article.section === item.id);
          return <section key={item.id} aria-labelledby={`help-section-${item.id}`} className="grid content-start gap-3 rounded-2xl border border-line bg-panel p-5">
            <h2 id={`help-section-${item.id}`} className="title-section"><RouteLink className={LINK} href={hrefFor(item.id)}>{item.title}</RouteLink></h2>
            <p className="text-sm text-muted">{item.summary}</p>
            <ul className="grid gap-1.5 text-sm">
              {own.slice(0, 6).map(article => <li key={article.id}><RouteLink className={LINK} href={hrefFor(article.id)}>{article.title}</RouteLink></li>)}
            </ul>
            {own.length > 6 ? <RouteLink className={`${LINK} text-sm font-semibold`} href={hrefFor(item.id)}>{t`All ${own.length} ${item.title} articles →`}</RouteLink> : null}
          </section>;
        })}
      </div>}
      {!signedIn && !loading ? <SignInNote memberHref={memberHref} /> : null}
    </div>
  </PublicLayout>;
}
