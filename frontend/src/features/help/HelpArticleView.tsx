import { PublicLayout } from "../../components/layouts";
import { RouteLink } from "../../components/ui/RouteLink";
import { HelpArticleBody } from "./HelpArticleBody";
import type { HelpChrome } from "./HelpIndex";
import type { HelpArticle, HelpSection } from "./helpTypes";

type Props = {
  chrome: HelpChrome;
  article: HelpArticle | undefined;
  section: HelpSection | undefined;
  /** Whether this reader may see the article (role, and the space's switches). */
  visible: boolean;
  loading: boolean;
  signedIn: boolean;
  memberHref: string;
  siblings: HelpArticle[];
  hrefFor: (target: string) => string;
};

const LINK = "rounded-control text-accent-ink underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

/** One article. A deep link the reader may not see explains why instead of failing silently. */
export function HelpArticleView({ chrome, article, section, visible, loading, signedIn, memberHref, siblings, hrefFor }: Props) {
  const home = { label: "Help", href: hrefFor("") };
  if (!article || !section) {
    return <PublicLayout {...chrome} header={{ title: "We couldn't find that article" }} breadcrumb={[home]} state={{ status: "ready" }}>
      <p className="text-muted">The link may be old, or the article moved. <RouteLink className={`${LINK} font-semibold underline`} href={hrefFor("")}>Browse the guide</RouteLink> or search it.</p>
    </PublicLayout>;
  }
  const crumbs = [home, { label: section.title, href: hrefFor(section.id) }, { label: article.title }];
  if (loading && !visible) return <PublicLayout {...chrome} header={{ title: article.title }} breadcrumb={crumbs} state={{ status: "loading" }}><span /></PublicLayout>;
  if (!visible) {
    return <PublicLayout {...chrome} header={{ eyebrow: section.title, title: article.title }} breadcrumb={crumbs} state={{ status: "ready" }}>
      <div className="grid gap-3 rounded-2xl border border-line bg-surface p-5">
        <p>This article is written for <strong>{section.title}</strong>, or for a feature this space has not switched on.</p>
        <p className="text-muted">{signedIn
          ? "Your account doesn't hold that role here. Ask your Space Manager if you think it should."
          : <>If you hold that role, <RouteLink className={`${LINK} font-semibold underline`} href={memberHref}>sign in</RouteLink> and open this link again.</>}</p>
      </div>
    </PublicLayout>;
  }
  return <PublicLayout {...chrome} header={{ eyebrow: section.title, title: article.title, subtitle: article.summary }} breadcrumb={crumbs} state={{ status: "ready" }}>
    <article className="grid gap-10">
      <HelpArticleBody body={article.body} hrefFor={hrefFor} />
      {siblings.length ? <nav aria-labelledby="help-more" className="grid gap-3 border-t border-line pt-6">
        <h2 id="help-more" className="title-section">More in {section.title}</h2>
        <ul className="grid gap-1.5 text-sm">
          {siblings.map(item => <li key={item.id}><RouteLink className={LINK} href={hrefFor(item.id)}>{item.title}</RouteLink></li>)}
        </ul>
      </nav> : null}
    </article>
  </PublicLayout>;
}
