import { t } from "@lingui/core/macro";
import { LogoLoader } from "../../components/LogoLoader";
import { lazy, Suspense } from "react";
import { Link, useParams } from "react-router-dom";
import { PageMetadata } from "../../components/PageMetadata";
import { DocArticle } from "./DocArticle";
import { DocsHome } from "./DocsHome";
import { DocsLayout } from "./DocsLayout";
import { findDoc } from "./docsIndex";

// The API reference renders from per-tag chunks generated out of openapi-schema.json at build time.
const ApiReferenceRoute = lazy(() => import("./apiReference/ApiReferenceRoute").then(m => ({ default: m.ApiReferenceRoute })));

export function DocsNotFound({ id }: { id: string }) {
  return <div className="sw-doc-notfound">
    <PageMetadata title={t`Page not found · Space Works docs`} description={t`This documentation page does not exist.`} path={`/docs/${id}`} noindex />
    <h1 className="sw-doc-title">{t`This page isn’t in the docs`}</h1>
    <p className="sw-doc-summary">{t`It may have moved or been renamed. Search for it, or start from the documentation home.`}</p>
    <p className="code-text text-sm text-muted">{`/docs/${id}`}</p>
    <Link to="/docs" className="desk-button-primary mt-6 w-fit">{t`Go to the documentation home`}</Link>
  </div>;
}

/** /docs → home; /docs/api/reference[/tag] → the generated API reference; /docs/<id> → a page; else not found. */
export function DocsPage() {
  const splat = (useParams()["*"] ?? "").replace(/\/+$/, "");
  const api = /^api\/reference(?:\/([^/]+))?$/.exec(splat);
  const entry = splat && !api ? findDoc(splat) : undefined;
  return <DocsLayout currentId={splat}>
    {openPalette => !splat ? <DocsHome onSearch={openPalette} />
      : api ? <Suspense fallback={<LogoLoader label={t`Loading the API reference…`} />}>
        <PageMetadata title={t`API reference · Space Works docs`} description={t`Every Space Works API endpoint, grouped by area.`} path={`/docs/${splat}`} />
        <ApiReferenceRoute tag={api[1]} /></Suspense>
      : entry ? <DocArticle key={entry.id} entry={entry} />
      : <DocsNotFound id={splat} />}
  </DocsLayout>;
}
