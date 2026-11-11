import { t } from "@lingui/core/macro";
import { ErrorBlock, Skeleton } from "../../../components/ui";
import type { TemplateDetail, Preview } from "./EmailTemplateEditor";

export function TemplateHeader({ detail, active, typeOverride, onActive }: { detail: TemplateDetail; active: boolean; typeOverride: boolean; onActive: (active: boolean) => void }) {
  return <div className="flex flex-wrap items-start justify-between gap-3">
    {detail.description ? <p className="max-w-3xl text-sm text-muted">{detail.description}</p> : null}
    <label className="flex min-h-11 max-w-xs items-start gap-3 text-sm text-ink">
      <input className="mt-1 h-5 w-5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" type="checkbox" checked={active} onChange={event => onActive(event.target.checked)} />
      <span><span className="font-semibold">{t`Use custom template`}</span>
        <span className="block text-xs text-muted">{typeOverride ? t`When off, the space default is sent (your text is kept). The email always sends.` : t`When off, the built-in default is sent (your text is kept). The email always sends.`}</span>
      </span>
    </label>
  </div>;
}

export function MergeFields({ detail, onInsert }: { detail: TemplateDetail; onInsert: (name: string) => void }) {
  return (
    <div className="grid gap-2">
      <h3 className="title-section">{t`Merge fields`}</h3>
      <div className="flex flex-wrap gap-2">
        {detail.fields.map((field) => (
          <button key={field.name} className="desk-button-ghost code-text text-xs" title={field.description} type="button" onClick={() => onInsert(field.name)}>
            {field.name}
          </button>
        ))}
      </div>
    </div>
  );
}

export function DefaultReference({ detail, typeOverride }: { detail: TemplateDetail; typeOverride: boolean }) {
  return (
    <div className="grid gap-3 rounded-md border border-line bg-bg p-4">
      <h3 className="title-section">{typeOverride ? t`Space default reference` : t`Built-in default reference`}</h3>
      <ReferenceBlock title={t`Subject`} value={detail.default_subject} />
      <ReferenceBlock title={t`Plain text`} value={detail.default_text} tall />
    </div>
  );
}

function ReferenceBlock({ title, value, tall = false }: { title: string; value: string; tall?: boolean }) {
  return (
    <div className="grid gap-2">
      <h4 className="title-section">{title}</h4>
      <pre className={`${tall ? "max-h-64 whitespace-pre-wrap" : ""} font-sans tabular-nums overflow-auto rounded-md border border-line bg-surface p-3 text-xs text-muted`}>{value || "-"}</pre>
    </div>
  );
}

export function PreviewPane({ preview, loading, error, onRetry }: { preview?: Preview; loading: boolean; error: Error | null; onRetry?: () => void }) {
  if (loading && !preview) return <Skeleton className="h-96 w-full" />;
  if (error) return <ErrorBlock error={new Error(t`Couldn't load the preview. Try again.`)} onRetry={onRetry} />;
  return (
    <div className="grid gap-3 rounded-md border border-line bg-bg p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="title-section">{t`Preview`}</h3>
        {loading ? <span className="text-xs text-muted">{t`Rendering…`}</span> : null}
      </div>
      <ReferenceBlock title={t`Subject`} value={preview?.subject ?? ""} />
      <ReferenceBlock title={t`Plain text`} value={preview?.text_body ?? ""} tall />
      {preview?.html_body ? (
        <div className="grid gap-2">
          <h4 className="title-section">HTML</h4>
          <iframe className="h-96 w-full rounded-md border border-line bg-panel" sandbox="" srcDoc={preview.html_body} title={t`Rendered email HTML preview`} />
        </div>
      ) : null}
    </div>
  );
}
