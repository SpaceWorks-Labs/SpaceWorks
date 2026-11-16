import { t } from "@lingui/core/macro";
import { useEffect, useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ConfirmDialog, SegmentedControl, SettingsRow, StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { LegalMarkdown } from "./LegalMarkdown";
import { LEGAL_SLUGS, legalTitle, type LegalPageBody, type LegalSlug } from "./legalApi";
import { BoxArt } from "../../components/BoxSpinner";

/**
 * Edit /privacy and /terms (parity A13). `platform`: the operator's text for every space (superadmin);
 * DELETE returns it to the shipped default. `space`: this space's own text; saving it blank clears it,
 * so its visitors see the platform text again. Markdown only; raw HTML is never rendered.
 */
export function LegalPagesEditor({ scope }: { scope: { kind: "platform" } | { kind: "space"; makerspaceId: number } }) {
  const [slug, setSlug] = useState<LegalSlug>("privacy");
  return <div className="grid gap-4 py-4">
    <SegmentedControl label={t`Page`} value={slug} onChange={value => setSlug(value as LegalSlug)}
      options={LEGAL_SLUGS.map(value => ({ value, label: legalTitle(value) }))} />
    <LegalPageForm key={slug} slug={slug} scope={scope} />
  </div>;
}

const SOURCE_LABEL = (): Record<LegalPageBody["source"], string> => ({
  space: t`This space's own text`, platform: t`Platform text`, default: t`Shipped default`,
});

function LegalPageForm({ slug, scope }: { slug: LegalSlug; scope: Parameters<typeof LegalPagesEditor>[0]["scope"] }) {
  const client = useQueryClient();
  const fieldId = useId();
  const path = scope.kind === "platform" ? `/admin/platform/legal-pages/${slug}` : `/admin/makerspace/${scope.makerspaceId}/legal-pages/${slug}`;
  const key = ["legal-page-editor", scope.kind, scope.kind === "space" ? scope.makerspaceId : 0, slug];
  const page = useQuery({ queryKey: key, queryFn: () => staffRequest<LegalPageBody>(path), retry: false });
  const [draft, setDraft] = useState("");
  const [preview, setPreview] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const own = scope.kind === "platform" ? page.data?.source === "platform" : page.data?.source === "space";
  // A space starts from blank (blank = use the platform text); the operator starts from what visitors see.
  const initial = page.data ? (own || scope.kind === "platform" ? page.data.markdown : "") : "";
  useEffect(() => { setDraft(initial); }, [initial]);
  const refresh = () => Promise.all([client.invalidateQueries({ queryKey: key }), client.invalidateQueries({ queryKey: ["legal-page", slug] })]);
  const save = useMutation({ mutationFn: () => staffRequest<LegalPageBody>(path, { method: "PUT", body: JSON.stringify({ markdown: draft }) }),
    onSuccess: data => { client.setQueryData(key, data); void refresh(); } });
  const reset = useMutation({ mutationFn: () => staffRequest<void>(path, { method: "DELETE" }), onSuccess: () => { setConfirmReset(false); void refresh(); } });
  const dirty = draft !== initial;
  const blankPlatform = scope.kind === "platform" && !draft.trim();
  return <SettingsRow label={legalTitle(slug)} htmlFor={fieldId}
    helper={scope.kind === "platform" ? t`Shown on every space that has not written its own. Markdown: # headings, lists, **bold** and links.`
      : t`Leave blank to show the platform's text. Markdown: # headings, lists, **bold** and links.`}>
    <form className="grid min-w-0 gap-3" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
      {page.data ? <div className="flex flex-wrap items-center gap-2">
        <StatusPill label={SOURCE_LABEL()[page.data.source]} tone={own ? "success" : "neutral"} />
        {page.data.updated_at && own ? <span className="text-sm text-muted">{t`Saved ${formatDateTime(page.data.updated_at)}`}</span> : null}
      </div> : null}
      {page.error ? <p role="alert" className="text-sm text-danger">{t`Couldn't load this page. Own pages may be switched off for this space.`}</p> : null}
      <SegmentedControl label={t`Editor view`} value={preview ? "preview" : "write"} onChange={value => setPreview(value === "preview")}
        options={[{ value: "write", label: t`Write` }, { value: "preview", label: t`Preview` }]} />
      {preview ? <div className="rounded-control border border-line bg-panel p-4">{draft.trim() ? <LegalMarkdown body={draft} />
        : <p className="text-sm text-muted">{scope.kind === "space" ? t`Visitors see the platform's text.` : t`Nothing to preview yet.`}</p>}</div>
        : <textarea id={fieldId} className="desk-input code-text min-h-72 text-sm" value={draft} maxLength={50000} disabled={!page.data || save.isPending}
          placeholder={scope.kind === "space" ? page.data?.markdown : undefined} onChange={event => { setDraft(event.target.value); save.reset(); }} />}
      {blankPlatform ? <p className="text-sm text-muted">{t`Write the page, or return it to the shipped default.`}</p> : null}
      {save.error || reset.error ? <p role="alert" className="text-sm text-danger">{(save.error ?? reset.error)?.message}</p> : null}
      {save.isSuccess && !dirty ? <p role="status" className="text-sm text-muted">{t`Saved. Visitors see the new text now.`}</p> : null}
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="desk-button-primary" disabled={!dirty || save.isPending || blankPlatform}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save page`}</button>
        {dirty ? <button type="button" className="desk-button" onClick={() => { setDraft(initial); save.reset(); }}>{t`Discard`}</button> : null}
        {scope.kind === "platform" && own ? <button type="button" className="desk-button" onClick={() => setConfirmReset(true)}>{t`Return to the shipped default`}</button> : null}
      </div>
    </form>
    <ConfirmDialog open={confirmReset} title={t`Return to the shipped default?`} message={t`Your text for this page is removed. Spaces without their own text show the default again.`}
      confirmLabel={t`Use the default`} tone="danger" pending={reset.isPending} onCancel={() => setConfirmReset(false)} onConfirm={() => reset.mutate()} />
  </SettingsRow>;
}
