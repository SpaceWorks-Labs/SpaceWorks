import { t } from "@lingui/core/macro";
import { ArrowLeft, ArrowRight, Pencil } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { PageMetadata } from "../../components/PageMetadata";
import { DocsToc } from "./DocsToc";
import { articleBody } from "./docsSource";
import { allDocs, DOCS_VERSION, groupAnchor, groupLabel, neighbours } from "./docsIndex";
import { editUrl } from "./docsLinks";
import type { DocEntry } from "./docsTypes";
import { loaders } from "virtual:spaceworks-docs-pages";

// The Markdown renderer (react-markdown + GFM) is its own chunk, so the docs home never loads it.
const DocsMarkdown = lazy(() => import("./DocsMarkdown").then(m => ({ default: m.DocsMarkdown })));

// Each page body is its own chunk, read from docs/ by the docs Vite plugin (scripts/docs-plugin.ts).
export function loadDocBody(source: string) {
  const loader = loaders[source];
  // i18n-ignore: internal error, never shown (the page shows its own translated error state)
  return loader ? loader().then(module => module.default) : Promise.reject(new Error(`Unpublished page ${source}`));
}

type Body = { status: "loading" } | { status: "error" } | { status: "ready"; text: string };

function useDocBody(entry: DocEntry, attempt: number): Body {
  const [body, setBody] = useState<Body & { source?: string }>({ status: "loading" });
  useEffect(() => {
    let live = true;
    setBody({ status: "loading" });
    loadDocBody(entry.source).then(raw => { if (live) setBody({ status: "ready", text: articleBody(raw), source: entry.source }); })
      .catch(() => { if (live) setBody({ status: "error" }); });
    return () => { live = false; };
  }, [entry.source, attempt]);
  return body;
}

/** Breadcrumbs, title, summary and meta; the body with its "On this page" rail; then previous / next. */
export function DocArticle({ entry }: { entry: DocEntry }) {
  const [attempt, setAttempt] = useState(0);
  const body = useDocBody(entry, attempt);
  const { hash } = useLocation();
  const [rendered, setRendered] = useState(false);
  const ready = body.status === "ready" && rendered;
  const markRendered = useCallback(() => setRendered(true), []);
  const { previous, next } = neighbours(entry.id);
  useEffect(() => {
    if (!ready) return;
    const target = hash ? document.getElementById(decodeURIComponent(hash.slice(1))) : null;
    if (target) target.scrollIntoView({ block: "start" });
    else window.scrollTo({ top: 0 });
  }, [ready, hash, entry.id]);
  return <div className="sw-doc-page">
    <PageMetadata title={t`${entry.title} · Space Works docs`} description={entry.summary || entry.title} path={`/docs/${entry.id}`} siteName="Space Works" />
    <article className="min-w-0" aria-labelledby="doc-title">
      <nav aria-label={t`Breadcrumb`} className="sw-doc-crumbs">
        <Link to="/docs">{t`Docs`}</Link><span aria-hidden="true">/</span>
        <Link to={`/docs#${groupAnchor(entry.group)}`}>{groupLabel(entry.group)}</Link><span aria-hidden="true">/</span>
        <span aria-current="page">{entry.title}</span>
      </nav>
      <h1 id="doc-title" className="sw-doc-title">{entry.title}</h1>
      {entry.summary ? <p className="sw-doc-summary">{entry.summary}</p> : null}
      <div className="sw-doc-meta">
        <span className="sw-doc-version">{t`Version ${DOCS_VERSION}`}</span>
        {entry.updated ? <span>{t`Updated ${entry.updated}`}</span> : null}
        <a href={editUrl(entry.source)} target="_blank" rel="noreferrer noopener" className="sw-doc-edit">
          <Pencil size={14} aria-hidden="true" />{t`Edit this page on GitHub`}<span className="sr-only">{t`(opens in a new tab)`}</span></a>
      </div>
      {body.status === "ready" ? <Suspense fallback={<p role="status" className="py-6 text-muted">{t`Loading page…`}</p>}><DocsMarkdown body={body.text} source={entry.source} index={allDocs} onRendered={markRendered} /></Suspense>
        : body.status === "error" ? <div role="alert" className="sw-doc-callout" data-kind="caution">
          <p className="sw-doc-callout-title">{t`This page could not be loaded.`}</p>
          <div className="sw-doc-callout-body"><p>{t`Check your connection and try again.`}</p>
            <button type="button" className="desk-button mt-3" onClick={() => setAttempt(value => value + 1)}>{t`Try again`}</button></div>
        </div>
        : <div role="status" className="grid gap-3 py-6" aria-label={t`Loading page`}>
          {[80, 95, 70, 88].map(width => <span key={width} className="block h-4 rounded bg-surface" style={{ width: `${width}%` }} />)}
        </div>}
      <nav aria-label={t`Previous and next pages`} className="sw-doc-pager">
        {previous ? <Link to={`/docs/${previous.id}`} rel="prev" className="sw-doc-pager-link">
          <span className="flex items-center gap-1 text-sm text-muted"><ArrowLeft size={14} aria-hidden="true" />{t`Previous`}</span>
          <span className="font-semibold text-ink">{previous.title}</span></Link> : <span />}
        {next ? <Link to={`/docs/${next.id}`} rel="next" className="sw-doc-pager-link sw-doc-pager-next">
          <span className="flex items-center justify-end gap-1 text-sm text-muted">{t`Next`}<ArrowRight size={14} aria-hidden="true" /></span>
          <span className="font-semibold text-ink">{next.title}</span></Link> : null}
      </nav>
    </article>
    <aside className="sw-doc-rail"><DocsToc headings={entry.headings} ready={ready} /></aside>
  </div>;
}
