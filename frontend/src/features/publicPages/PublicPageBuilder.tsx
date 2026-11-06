import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { PageMetadata } from "../../components/PageMetadata";
import { ErrorBlock, StatusPill } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { PageEditorAssets } from "./PageEditorAssets";
import { PageHandleForm } from "./PageHandleForm";
import { PagePresentationForm } from "./PagePresentationForm";
import { PagePreview } from "./PagePreview";
import { PageRevisionHistory } from "./PageRevisionHistory";
import { PageSectionsEditor } from "./PageSectionsEditor";
import { usePageEditor, usePageOperation, type PageOperation } from "./pageApi";
import type { EditorState, PageDocument, PageOwner, PreviewProjection } from "./pageTypes";

export function PublicPageBuilder({ owner }: { owner: PageOwner }) {
  return <Builder key={`${owner.kind}-${owner.id}`} owner={owner} />;
}
function Builder({ owner }: { owner: PageOwner }) {
  const query = usePageEditor(owner);
  const operation = usePageOperation(owner);
  const [local, setLocal] = useState<{ base: EditorState; document: PageDocument } | null>(null);
  const [preview, setPreview] = useState<PreviewProjection | null>(null);
  const [message, setMessage] = useState("");
  const [stale, setStale] = useState(false);
  useEffect(() => {
    if (query.data) setLocal(current => current && JSON.stringify(current.document) !== JSON.stringify(current.base.document)
      ? current : { base: query.data!, document: query.data!.document });
  }, [query.data]);
  const state = query.error ? undefined : query.data;
  const dirty = Boolean(local && JSON.stringify(local.document) !== JSON.stringify(local.base.document));
  // While an operation settles the editor cache can lead the local base by one version; that is not a conflict.
  const conflict = stale || Boolean(!operation.isPending && local && state && local.base.version !== state.version);
  const pending = operation.isPending;
  const disabled = pending || !state?.capabilities.can_edit_details;
  const change = (document: PageDocument) => { setLocal(current => current ? { ...current, document } : current); setPreview(null); setMessage(""); };
  const run = (input: PageOperation) => operation.mutate(input, {
    onSuccess: result => {
      if (input.action === "preview") { setPreview(result as PreviewProjection); setMessage(t`Preview validated. This is still a draft.`); return; }
      const saved = result as EditorState; setLocal({ base: saved, document: saved.document }); setStale(false); setPreview(null);
      setMessage(input.action === "save" ? t`Draft saved. Your published page stays unchanged until you publish.`
        : input.action === "publish" ? t`Latest saved draft published.` : input.action === "unpublish" || input.action === "release_handle" ? t`Page unpublished. Your draft and history are retained.` : t`Page settings updated.`);
    },
    onError: error => {
      if (error instanceof StructuredApiError && error.code === "stale_version") { setStale(true); void query.refetch(); }
    },
  });
  if (query.isLoading || !local && !query.error) return <p role="status">{t`Loading public page builder…`}</p>;
  if (query.error instanceof StructuredApiError && query.error.status === 403) return <p className="text-sm text-muted">{owner.kind === "makerspace"
    ? t`Only this makerspace's Space Manager can edit the public page.` : t`Only this organization's profile managers can edit the public page.`}</p>;
  if (query.error) return <ErrorBlock error={query.error} onRetry={() => { void query.refetch(); }} />;
  if (!state || !local) return null;
  const document = local.document;
  const caps = state.capabilities;
  const saved = Boolean(state.draft_revision_id);
  const currentPublished = saved && state.draft_revision_id === state.published_revision_id;
  return <section className="grid min-w-0 gap-6 py-4" aria-label={t`Public page builder`}>
    <PageMetadata title={t`Public page builder · Space Works`} description={t`Private draft editor`} path={window.location.pathname} noindex />
    <div className="flex flex-wrap items-center gap-3"><h2 className="title-panel">{t`Public page builder`}</h2><StatusPill label={state.published_revision_id ? currentPublished ? t`Published` : t`Draft changes pending` : t`Unpublished`} tone={currentPublished ? "success" : "neutral"} /></div>
    <p className="text-sm text-muted">{t`Save creates a private draft. Publish selects the latest saved draft. Public collections and member links are checked live by the server.`}</p>
    {operation.error ? <ErrorBlock error={operation.error} /> : null}
    <p role="status" aria-live="polite" className="text-sm text-brand-ink">{message}</p>
    {conflict ? <div role="alert" className="grid gap-3 rounded-xl border border-warn bg-warn-soft p-4 text-warn-ink">
      <p>{t`The server version changed. Your local edits are retained. Reload the saved version or reapply your edits to the latest version, then review and save.`}</p>
      <div className="flex flex-wrap gap-2"><button className="desk-button" type="button" disabled={pending || query.isFetching || !state} onClick={() => { setLocal({ base: state, document: state.document }); setStale(false); setPreview(null); operation.reset(); }}>{t`Discard edits and reload`}</button>
        <button className="desk-button" type="button" disabled={pending || query.isFetching || local.base.version === state.version} onClick={() => { setLocal({ base: state, document }); setStale(false); setPreview(null); operation.reset(); }}>{t`Reapply local edits for review`}</button></div>
    </div> : null}
    <PageHandleForm key={state.handle ?? "unclaimed"} state={state} owner={owner} disabled={disabled || dirty || conflict} run={run} />
    <form className="grid gap-6" onSubmit={e => { e.preventDefault(); if (!disabled && !conflict) run({ action: "save", version: local.base.version, document }); }}>
      <PagePresentationForm document={document} assets={state.assets} choices={caps.palette_choices} disabled={disabled} onChange={change} />
      <PageSectionsEditor document={document} assets={state.assets} allowed={caps.allowed_section_types} required={caps.required_groups} maxSections={state.limits.sections} kind={owner.kind} disabled={disabled} onChange={change} />
      <div className="flex flex-wrap gap-2 border-t border-line pt-4">
        <button type="submit" className="desk-button-primary" disabled={disabled || conflict}>{operation.isPending && operation.variables?.action === "save" ? t`Saving draft…` : t`Save draft`}</button>
        <button type="button" className="desk-button" disabled={pending || conflict || !caps.can_edit_details} onClick={() => run({ action: "preview", version: local.base.version, document })}>{t`Validate and preview draft`}</button>
        <button type="button" className="desk-button" disabled={pending || dirty || conflict || !caps.can_publish || !state.handle || !saved || currentPublished} onClick={() => { if (state.draft_revision_id) run({ action: "publish", version: state.version, draft_revision_id: state.draft_revision_id }); }}>{t`Publish saved draft`}</button>
        {state.published_revision_id ? <button type="button" className="desk-button" disabled={pending || dirty || conflict || !caps.can_publish} onClick={() => run({ action: "unpublish", version: state.version })}>{t`Unpublish page`}</button> : null}
      </div>
      {dirty ? <p className="text-sm text-muted">{t`Save changes before publishing, claiming a handle or uploading images.`}</p> : null}
      {!state.handle ? <p className="text-sm text-muted">{t`Claim a handle before publishing.`}</p> : null}
    </form>
    {preview ? <PagePreview page={preview} /> : null}
    <PageEditorAssets state={state} pending={pending || conflict} dirty={dirty} run={run} />
    <PageRevisionHistory owner={owner} />
  </section>;
}
