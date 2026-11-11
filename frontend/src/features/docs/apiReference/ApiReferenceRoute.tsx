import { plural, t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { loaders, tags, version } from "virtual:spaceworks-api-tags";
import type { ApiTagPayload, ApiTagSummary } from "./apiReferenceModel";
import { ApiOperationSection, MethodPill } from "./ApiOperationSection";

export const API_REFERENCE_PATH = "/docs/api/reference";

// One promise per tag for the life of the page: revisiting a tag never refetches its chunk.
const cache = new Map<string, Promise<ApiTagPayload>>();
function loadTag(slug: string) {
  if (!cache.has(slug)) cache.set(slug, loaders[slug]().then(module => module.default));
  return cache.get(slug)!;
}

function ApiReferenceIndex() {
  const groups = new Map<string, ApiTagSummary[]>();
  tags.forEach(tag => groups.set(tag.group, [...(groups.get(tag.group) ?? []), tag]));
  const operations = tags.reduce((sum, tag) => sum + tag.count, 0);
  return <div className="grid gap-10">
    <header className="grid max-w-[72ch] gap-3">
      <h1 className="title-page">{t`API reference`}</h1>
      <p className="text-base leading-7 text-muted">{t`Every endpoint this server exposes, generated from its OpenAPI schema (version ${version}, ${operations} endpoints). Each page lists what an endpoint takes, what it returns, who may call it and a curl request to try it.`}</p>
    </header>
    {[...groups].map(([group, items]) => <section key={group || "other"} aria-label={group || t`Other`} className="grid gap-3">
      <h2 className="title-panel">{group || t`Other`}</h2>
      <ul className="grid gap-x-8 sm:grid-cols-2">{items.map(tag => <li key={tag.slug} className="border-t border-line">
        <Link to={`${API_REFERENCE_PATH}/${tag.slug}`} className="flex min-h-11 items-baseline justify-between gap-3 rounded-control py-2.5 hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
          <span className="grid min-w-0 gap-0.5">
            <span className="font-semibold text-ink">{tag.name}</span>
            {tag.description ? <span className="text-sm text-muted">{tag.description}</span> : null}
          </span>
          <span className="shrink-0 text-sm tabular-nums text-muted">{plural(tag.count, { one: "# endpoint", other: "# endpoints" })}</span>
        </Link>
      </li>)}</ul>
    </section>)}
  </div>;
}

function BackLink() {
  return <Link to={API_REFERENCE_PATH} className="text-sm font-semibold text-accent-ink underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">{t`All API sections`}</Link>;
}

function ApiTagPage({ summary }: { summary: ApiTagSummary }) {
  const { hash } = useLocation();
  const [state, setState] = useState<{ slug: string; payload?: ApiTagPayload; failed?: boolean }>({ slug: summary.slug });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    loadTag(summary.slug).then(payload => { if (live) setState({ slug: summary.slug, payload }); })
      .catch(() => { cache.delete(summary.slug); if (live) setState({ slug: summary.slug, failed: true }); });
    return () => { live = false; };
  }, [summary.slug, attempt]);
  const payload = state.slug === summary.slug ? state.payload : undefined;
  useEffect(() => {
    if (payload && hash) document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView();
  }, [payload, hash]);
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  return <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_16rem] xl:gap-12">
    <div className="grid min-w-0 gap-8">
      <header className="grid max-w-[72ch] gap-3">
        <BackLink />
        <h1 className="title-page">{summary.name}</h1>
        {summary.description ? <p className="text-base leading-7 text-muted">{summary.description}</p> : null}
        <p className="text-sm text-muted">{summary.group ? `${summary.group} · ` : ""}{plural(summary.count, { one: "# endpoint", other: "# endpoints" })}</p>
      </header>
      {state.failed && state.slug === summary.slug ? <div role="alert" className="grid justify-items-start gap-3 rounded-xl border border-danger-line p-4">
        <p className="text-sm text-danger">{t`Couldn't load this section. Check your connection and try again.`}</p>
        <button type="button" className="desk-button" onClick={() => { setState({ slug: summary.slug }); setAttempt(n => n + 1); }}>{t`Try again`}</button>
      </div> : !payload ? <p role="status" className="text-sm text-muted">{t`Loading endpoints…`}</p>
        : payload.operations.map(operation => <ApiOperationSection key={`${operation.method}:${operation.path}`} operation={operation}
          schemas={payload.schemas} schemes={payload.securitySchemes} origin={origin} />)}
    </div>
    {payload ? <nav aria-label={t`On this page`} className="hidden xl:block">
      <div className="sticky top-24 grid max-h-[calc(100dvh-8rem)] gap-2 overflow-y-auto pb-4">
        <p className="text-sm font-semibold text-ink">{t`On this page`}</p>
        <ul className="grid gap-1 text-sm">{payload.operations.map(operation => <li key={`${operation.method}:${operation.path}`}>
          <a href={`#${operation.operationId}`} className="flex items-start gap-2 rounded-control py-1 text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
            <MethodPill method={operation.method} /><span className="min-w-0">{operation.summary || operation.operationId}</span>
          </a>
        </li>)}</ul>
      </div>
    </nav> : null}
  </div>;
}

/** /docs/api/reference (every section) and /docs/api/reference/<tag> (one section's endpoints). */
export function ApiReferenceRoute({ tag }: { tag?: string }) {
  if (!tag) return <ApiReferenceIndex />;
  const summary = tags.find(item => item.slug === tag);
  if (!summary) {
    return <div className="grid max-w-[72ch] justify-items-start gap-3">
      <h1 className="title-page">{t`API section not found`}</h1>
      <p className="text-base text-muted">{t`There is no API section called “${tag}” on this server.`}</p>
      <BackLink />
    </div>;
  }
  return <ApiTagPage key={summary.slug} summary={summary} />;
}
