import { t } from "@lingui/core/macro";
import type { ApiOperation, ApiResponse, ApiSecurityScheme } from "./apiReferenceModel";
import { ApiCopyBlock } from "./ApiCopyBlock";
import { buildCurl } from "./apiCurl";
import { SchemaBlock } from "./ApiSchemaTree";
import { typeLabel, type Schemas } from "./apiSchema";
import { toneMarkClasses } from "../../../components/ui/tones";
import type { Tone } from "../../../components/ui/types";

const METHOD_TONES: Record<string, Tone> = { GET: "info", POST: "success", PUT: "warn", PATCH: "warn", DELETE: "danger" };

export function MethodPill({ method }: { method: string }) {
  return <span className={`inline-flex min-h-6 shrink-0 items-center rounded-full border px-2 text-xs font-bold tracking-[0.04em] ${toneMarkClasses[METHOD_TONES[method] ?? "neutral"]}`}>{method}</span>;
}

function Paragraphs({ text }: { text: string }) {
  return <div className="grid max-w-[72ch] gap-2 text-sm leading-6 text-muted">
    {text.split(/\n{2,}/).map((part, index) => <p key={index} className="whitespace-pre-line [overflow-wrap:anywhere]">{part}</p>)}
  </div>;
}

function Auth({ operation, schemes }: { operation: ApiOperation; schemes: { [name: string]: ApiSecurityScheme } }) {
  const names = operation.security;
  if (!names.length) return <p className="text-sm text-muted">{t`No sign-in needed.`}</p>;
  return <details className="text-sm">
    <summary className="cursor-pointer rounded-control font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
      {operation.anonymous ? t`Sign-in optional · ${names.join(", ")}` : t`Sign-in required · ${names.join(", ")}`}
    </summary>
    <ul className="mt-2 grid gap-2">{names.map(name => <li key={name} className="text-muted">
      <span className="code-text font-semibold text-ink">{name}</span>
      {schemes[name]?.description ? <span> — {schemes[name].description}</span> : null}
    </li>)}</ul>
  </details>;
}

function ResponseList({ responses, schemas }: { responses: ApiResponse[]; schemas: Schemas }) {
  return <ul className="grid gap-4">{responses.map(response => <li key={response.status} className="grid gap-2">
    <p className="flex flex-wrap items-baseline gap-2 text-sm">
      <span className="code-text font-bold text-ink">{response.status}</span>
      <span className="text-muted">{response.description}</span>
    </p>
    {Object.entries(response.content ?? {}).map(([type, schema]) => <SchemaBlock key={type} schema={schema} schemas={schemas} mediaType={type} />)}
  </li>)}</ul>;
}

/** One endpoint: what it does, who may call it, what it takes, what it returns and a curl to try it. */
export function ApiOperationSection({ operation, schemas, schemes, origin }: {
  operation: ApiOperation; schemas: Schemas; schemes: { [name: string]: ApiSecurityScheme }; origin: string;
}) {
  const success = operation.responses.filter(response => !/^[45]/.test(response.status));
  const errors = operation.responses.filter(response => /^[45]/.test(response.status));
  const headingId = `${operation.operationId}-title`;
  return <section id={operation.operationId} aria-labelledby={headingId} className="grid scroll-mt-24 gap-5 border-t border-line pt-8">
    <header className="grid gap-2">
      <h2 id={headingId} className="title-panel">{operation.summary || operation.operationId}</h2>
      <p className="flex min-w-0 flex-wrap items-center gap-2">
        <MethodPill method={operation.method} />
        <span className="code-text min-w-0 text-sm text-ink [overflow-wrap:anywhere]">{operation.path}</span>
      </p>
      <p className="code-text text-xs text-muted">{operation.operationId}</p>
    </header>
    {operation.description ? <Paragraphs text={operation.description} /> : null}
    <Auth operation={operation} schemes={schemes} />
    {operation.parameters.length ? <div className="grid gap-2">
      <h3 className="title-section">{t`Parameters`}</h3>
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[560px] text-left text-sm">
          <thead className="bg-surface text-muted"><tr>
            <th scope="col" className="px-3 py-2 font-semibold">{t`Name`}</th>
            <th scope="col" className="px-3 py-2 font-semibold">{t`In`}</th>
            <th scope="col" className="px-3 py-2 font-semibold">{t`Type`}</th>
            <th scope="col" className="px-3 py-2 font-semibold">{t`Description`}</th>
          </tr></thead>
          <tbody>{operation.parameters.map(param => <tr key={`${param.in}:${param.name}`} className="border-t border-line align-top">
            <td className="px-3 py-2"><span className="code-text font-semibold text-ink">{param.name}</span>
              {param.required ? <span className="ml-2 rounded-full bg-warn px-2 text-xs font-semibold text-on-warn">{t`required`}</span> : null}</td>
            <td className="px-3 py-2 text-muted">{param.in}</td>
            <td className="code-text px-3 py-2 text-muted">{param.schema ? typeLabel(param.schema, schemas) : ""}</td>
            <td className="max-w-[48ch] px-3 py-2 text-muted [overflow-wrap:anywhere]">{param.description}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </div> : null}
    <div className="grid gap-2">
      <h3 className="title-section">{t`Request body`}</h3>
      {operation.notes.request ? <p className="text-sm text-muted">{operation.notes.request}</p> : null}
      {operation.requestBody ? <>
        <p className="text-sm text-muted">{operation.requestBody.required ? t`Required.` : t`Optional.`}</p>
        {Object.entries(operation.requestBody.content).map(([type, schema]) => <SchemaBlock key={type} schema={schema} schemas={schemas} mediaType={type} />)}
      </> : operation.notes.request ? null : <p className="text-sm text-muted">{t`No request body.`}</p>}
    </div>
    <div className="grid gap-2">
      <h3 className="title-section">{t`Responses`}</h3>
      {operation.notes.response ? <p className="text-sm text-muted">{operation.notes.response}</p> : null}
      {operation.notes.noResponseBody ? <p className="text-sm text-muted">{t`No response body.`}</p> : null}
      <ResponseList responses={success} schemas={schemas} />
    </div>
    {errors.length ? <div className="grid gap-2">
      <h3 className="title-section">{t`Errors`}</h3>
      <ul className="grid gap-1 text-sm">{errors.map(response => <li key={response.status} className="flex flex-wrap items-baseline gap-2">
        <span className="code-text font-bold text-ink">{response.status}</span>
        <span className="text-muted">{response.description}</span>
        {Object.values(response.content ?? {}).filter(Boolean).slice(0, 1).map(schema => <span key="type" className="code-text text-muted">· {typeLabel(schema!, schemas)}</span>)}
      </li>)}</ul>
    </div> : null}
    <ApiCopyBlock label={t`Example request (curl)`} code={buildCurl(operation, schemas, origin)} />
  </section>;
}
