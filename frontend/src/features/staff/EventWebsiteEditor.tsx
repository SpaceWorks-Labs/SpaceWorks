import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import { Field, SettingsSection, Skeleton, StatusPill } from "../../components/ui";
import type { EventWebsite, WebsiteTarget } from "../events/websiteTypes";
import { PublicEventWebsite } from "../events/PublicEventWebsite";
import { EventWebsiteSections } from "./EventWebsiteSections";
import { EventWebsiteSchedule } from "./EventWebsiteSchedule";
import { useEventWebsite, useWebsiteAsset, useWebsiteRelease, useWebsiteSave, websiteKey } from "./eventWebsiteApi";
import { eventErrorText } from "./eventUi";
import { PageImage } from "../publicPages/PageImage";
import { EventWebsiteLayout } from "./EventWebsiteLayout";
import { websiteDraftPreview, type InheritedCover } from "../events/websiteDraftPreview";
import { EventWebsiteEditorial } from "./EventWebsiteEditorial";

type EditorProps = {
  target: WebsiteTarget; canEdit: boolean; canPublish: boolean; status: string;
  /** The effective event (or series) photo and title, which an "inherit" cover shows first. */
  inheritedImage?: { url: string | null; alt: string };
};

export function EventWebsiteEditor(props: EditorProps) {
  return <WebsiteDraftEditor key={JSON.stringify(websiteKey(props.target))} {...props} />;
}

function WebsiteDraftEditor({ target, canEdit, canPublish, status, inheritedImage }: EditorProps) {
  const query = useEventWebsite(target);
  const [local, setLocal] = useState<{ base: EventWebsite; draft: EventWebsite } | null>(null);
  const draft = local?.draft;
  const setDraft = (value: EventWebsite) => setLocal((current) => current ? { ...current, draft: value } : current);
  const [preview, setPreview] = useState(false);
  const [alt, setAlt] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [replaceId, setReplaceId] = useState<number | undefined>();
  const save = useWebsiteSave(target);
  const release = useWebsiteRelease(target);
  const asset = useWebsiteAsset(target);
  // Same fallback chain as the published projection; the makerspace artwork loads only for the preview.
  const space = useQuery({ queryKey: ["makerspace-settings", target.makerspaceId], enabled: preview && !inheritedImage?.url, retry: false,
    queryFn: () => staffRequest<{ cover_image_url?: string | null; logo_url?: string | null }>(`/admin/makerspaces/${target.makerspaceId}`) });
  const inheritedUrl = inheritedImage?.url || space.data?.cover_image_url || space.data?.logo_url;
  const inherited: InheritedCover = inheritedUrl ? { url: inheritedUrl, alt: inheritedImage?.alt ?? "" } : null;
  useEffect(() => {
    if (query.data) {
      const latest = query.data;
      setLocal((current) => current && JSON.stringify(current.draft) !== JSON.stringify(current.base)
        ? current : { base: latest, draft: latest });
    }
  }, [query.data]);
  canEdit = canEdit && (query.data?.capabilities?.can_edit_details ?? true);
  canPublish = canPublish && (query.data?.capabilities?.can_publish_schedule ?? true);
  const terminal = status === "cancelled" || status === "completed";
  const pending = save.isPending || release.isPending || asset.isPending;
  const dirty = Boolean(local && JSON.stringify(local.draft) !== JSON.stringify(local.base));
  const conflict = dirty && JSON.stringify(local?.base) !== JSON.stringify(query.data);
  const error = query.error || save.error || release.error || asset.error;
  return <section className="grid min-w-0 gap-6" aria-labelledby="event-website-title">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 flex-1 basis-64"><div className="flex flex-wrap items-center gap-2"><h2 id="event-website-title" className="title-panel">Event website</h2>
        {draft && !query.error ? <StatusPill label={draft.released ? "Released" : "Unreleased"} tone={draft.released ? "success" : "neutral"} /> : null}</div>
        <p className="mt-1 text-sm text-muted">Saving creates a draft. Release publishes the latest saved draft; an already released website keeps its previous snapshot until you release again.</p></div>
      {draft && !query.error ? <button className="desk-button" type="button" aria-pressed={preview} onClick={() => setPreview(!preview)}>{preview ? "Hide draft preview" : "Preview draft sections"}</button> : null}
    </div>
    {query.isLoading ? <div role="status" className="grid gap-3"><span className="sr-only">Loading website…</span><Skeleton className="h-24 w-full" /><Skeleton className="h-48 w-full" /></div> : null}
    {error ? <p role="alert" className="text-sm text-danger">{eventErrorText(error)}</p> : null}
    {query.error ? <button className="desk-button justify-self-start" type="button" onClick={() => query.refetch()}>Retry website</button> : null}
    {draft && !query.error ? <div className="grid min-w-0 gap-6">
      <p className="text-sm text-ink">{draft.released ? "Website released" : "Website unreleased"}{draft.inherited ? " · Inherited from series; saving creates a private occurrence override." : ""}</p>
      {draft.released && draft.draft_revision_id !== draft.published_revision_id ? <p role="status" className="text-sm text-warn-ink">Saved draft changes are waiting for release.</p> : null}
      {conflict ? <div role="status" className="grid gap-3 rounded-xl border border-warn bg-warn-soft p-4 text-sm text-warn-ink">
        <p>The website changed on the server. Your unsaved draft is retained with its original revision ({draft.revision}). Reload the latest version to resolve the conflict before saving.</p>
        <button className="desk-button justify-self-start" type="button" disabled={pending || !query.data} onClick={() => {
          if (query.data) setLocal({ base: query.data, draft: query.data });
        }}>Discard draft and reload latest</button>
      </div> : null}
      {preview ? <div role="region" aria-label="Event draft preview" className="min-w-0 rounded-xl border border-dashed border-line bg-bg p-4">
        <p className="eyebrow mb-3">Draft preview · not released</p>
        <PublicEventWebsite website={websiteDraftPreview(draft, target, inherited)} image={(url, description) => <PageImage url={url} alt={description} token={String(draft.revision)} privatePreview />} />
      </div> : null}
      <form className="grid min-w-0 gap-6" onSubmit={(e) => { e.preventDefault(); if (conflict) return; save.mutate(draft, {
        onSuccess: (saved) => setLocal({ base: saved, draft: saved }),
      }); }}>
        <EventWebsiteLayout page={draft} onChange={setDraft} disabled={!canEdit || pending || terminal} />
        <EventWebsiteEditorial page={draft} target={target} onChange={setDraft} disabled={!canEdit || pending || terminal} />
        <EventWebsiteSections page={draft} target={target} onChange={setDraft} disabled={!canEdit || pending || terminal} />
        <EventWebsiteSchedule page={draft} target={target} onChange={setDraft} disabled={!canPublish || pending || terminal} saved={!dirty && draft.revision > 0} />
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-line pt-4">
          {dirty ? <p className="mr-auto text-sm text-muted">Save the website before releasing it or changing images.</p> : null}
          {canPublish && !terminal ? <><button className="desk-button" type="button" disabled={pending || dirty || conflict || draft.inherited || !draft.revision || status !== "published"} onClick={() => release.mutate({ released: true, revision: draft.revision })}>Release saved draft</button>
            {draft.released ? <button className="desk-button" type="button" disabled={pending || dirty || conflict || draft.inherited} onClick={() => release.mutate({ released: false, revision: draft.revision })}>Unrelease website</button> : null}</> : null}
          <button className="desk-button-primary" type="submit" disabled={pending || terminal || conflict || (!canEdit && !canPublish)}>{save.isPending ? "Saving…" : draft.inherited ? "Save occurrence override" : "Save website"}</button>
        </div>
      </form>
      {canEdit && !terminal ? <SettingsSection title="Private website images">
        <form className="grid gap-4 py-5 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); if (!file) return; const data = new FormData(); data.set("file", file); data.set("alt_text", alt); data.set("revision", String(draft.revision)); if (replaceId) data.set("replace_id", String(replaceId)); asset.mutate(data); }}>
          <Field label="Image description"><input className="desk-input w-full min-w-0" required maxLength={200} value={alt} onChange={(e) => setAlt(e.target.value)} /></Field>
          <Field label="Replace image"><select className="desk-input w-full min-w-0" value={replaceId ?? ""} onChange={(e) => setReplaceId(e.target.value ? Number(e.target.value) : undefined)}><option value="">Upload new image</option>{draft.assets?.map((image) => <option key={image.id} value={image.id}>{image.alt_text}</option>)}</select></Field>
          <Field label="Image file" className="sm:col-span-2"><input className="desk-input w-full min-w-0" type="file" required accept="image/jpeg,image/png,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          <button className="desk-button justify-self-start sm:col-span-2" type="submit" disabled={pending || dirty || Boolean(replaceId && draft.inherited)}>{asset.isPending ? "Uploading…" : "Upload image (up to 5 MB)"}</button>
          {draft.assets?.length ? <ul className="grid gap-2 sm:col-span-2" aria-label="Website images">{draft.assets.map((image) => <li key={image.id} className="flex min-w-0 flex-wrap items-center justify-between gap-2 rounded-xl border border-line p-3">
            <span className="min-w-0 break-words text-sm text-ink">{image.alt_text}</span>
            <button className="desk-button-danger-outline" type="button" disabled={pending || dirty || draft.inherited || image.pinned} onClick={() => asset.mutate(image.id)}>Delete {image.alt_text}{image.pinned ? " (retained by a revision)" : ""}</button>
          </li>)}</ul> : null}
        </form>
      </SettingsSection> : null}
    </div> : null}
  </section>;
}
