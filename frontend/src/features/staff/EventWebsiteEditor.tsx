import { useEffect, useState } from "react";
import type { EventWebsite, WebsiteTarget } from "../events/websiteTypes";
import { PublicEventWebsite } from "../events/PublicEventWebsite";
import { EventWebsiteSections } from "./EventWebsiteSections";
import { EventWebsiteSchedule } from "./EventWebsiteSchedule";
import { useEventWebsite, useWebsiteAsset, useWebsiteRelease, useWebsiteSave, websiteKey } from "./eventWebsiteApi";
import { eventErrorText } from "./eventUi";
import { PrivateWebsiteImage } from "./PrivateWebsiteImage";
import { EventWebsiteLayout } from "./EventWebsiteLayout";
import { previewSessions } from "../events/websiteProgramme";

type EditorProps = {
  target: WebsiteTarget; canEdit: boolean; canPublish: boolean; status: string;
};

export function EventWebsiteEditor(props: EditorProps) {
  return <WebsiteDraftEditor key={JSON.stringify(websiteKey(props.target))} {...props} />;
}

function WebsiteDraftEditor({ target, canEdit, canPublish, status }: EditorProps) {
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
  useEffect(() => {
    if (query.data) {
      const latest = query.data;
      setLocal((current) => current && JSON.stringify(current.draft) !== JSON.stringify(current.base)
        ? current : { base: latest, draft: latest });
    }
  }, [query.data]);
  const terminal = status === "cancelled" || status === "completed";
  const pending = save.isPending || release.isPending || asset.isPending;
  const dirty = Boolean(local && JSON.stringify(local.draft) !== JSON.stringify(local.base));
  const conflict = dirty && JSON.stringify(local?.base) !== JSON.stringify(query.data);
  const error = query.error || save.error || release.error || asset.error;
  return <details className="rounded-xl border border-border p-4"><summary className="cursor-pointer font-semibold">Event website</summary>
    {query.isLoading ? <p role="status">Loading website…</p> : null}
    {error ? <p role="alert" className="mt-2 text-danger">{eventErrorText(error)}</p> : null}
    {query.error ? <button className="desk-button" type="button" onClick={() => query.refetch()}>Retry website</button> : null}
    {draft && !query.error ? <div className="mt-3 grid gap-4">
      <p>{draft.released ? "Website released" : "Website unreleased"}{draft.inherited ? " · Inherited from series; saving creates a private occurrence override." : ""}</p>
      <p className="text-sm text-muted">Only published sections on a released page appear publicly. Existing public event details and cover images remain visible independently.</p>
      {conflict ? <div role="status">
        <p>The website changed on the server. Your unsaved draft is retained with its original revision ({draft.revision}). Reload the latest version to resolve the conflict before saving.</p>
        <button className="desk-button" type="button" disabled={pending || !query.data} onClick={() => {
          if (query.data) setLocal({ base: query.data, draft: query.data });
        }}>Discard draft and reload latest</button>
      </div> : null}
      <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); if (conflict) return; save.mutate(draft, {
        onSuccess: (saved) => setLocal({ base: saved, draft: saved }),
      }); }}>
        <EventWebsiteLayout page={draft} onChange={setDraft} disabled={!canEdit || pending || terminal} />
        <EventWebsiteSections page={draft} target={target} onChange={setDraft} disabled={!canEdit || pending || terminal} />
        <EventWebsiteSchedule page={draft} target={target} onChange={setDraft} disabled={!canPublish || pending || terminal} saved={!dirty && draft.revision > 0} />
        <button className="desk-button-primary w-fit" disabled={pending || terminal || conflict || (!canEdit && !canPublish)}>{save.isPending ? "Saving…" : draft.inherited ? "Save occurrence override" : "Save website"}</button>
      </form>
      {canEdit && !terminal ? <form className="grid gap-2" onSubmit={(e) => { e.preventDefault(); if (!file) return; const data = new FormData(); data.set("file", file); data.set("alt_text", alt); if (replaceId) data.set("replace_id", String(replaceId)); asset.mutate(data); }}>
        <h4 className="font-semibold">Private website images</h4>
        <label>Image description<input className="desk-input" required maxLength={200} value={alt} onChange={(e) => setAlt(e.target.value)} /></label>
        <label>Image file<input className="desk-input" type="file" required accept="image/jpeg,image/png,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
        <label>Replace image<select className="desk-input" value={replaceId ?? ""} onChange={(e) => setReplaceId(e.target.value ? Number(e.target.value) : undefined)}><option value="">Upload new image</option>{draft.assets?.map((image) => <option key={image.id} value={image.id}>{image.alt_text}</option>)}</select></label>
        <button className="desk-button w-fit" disabled={pending || dirty || Boolean(replaceId && draft.inherited)}>{asset.isPending ? "Uploading…" : "Upload image (up to 5 MB)"}</button>
        {draft.assets?.map((image) => <div key={image.id} className="flex items-center gap-2"><span>{image.alt_text}</span><button className="desk-button-danger" type="button" disabled={pending || dirty || draft.inherited} onClick={() => asset.mutate(image.id)}>Delete {image.alt_text}</button></div>)}
      </form> : null}
      {canPublish && !terminal ? <button className="desk-button w-fit" type="button" disabled={pending || dirty || draft.inherited || !draft.revision || status !== "published"} onClick={() => release.mutate({ released: !draft.released, revision: draft.revision })}>{draft.released ? "Unrelease website" : "Release website"}</button> : null}
      <button className="desk-button w-fit" type="button" onClick={() => setPreview(!preview)}>{preview ? "Hide released-content preview" : "Preview published sections"}</button>
      {preview ? <PublicEventWebsite website={{ ...draft, sessions: previewSessions(draft.sessions) }} image={(url, description) => <PrivateWebsiteImage url={url} alt={description} />} /> : null}
    </div> : null}
  </details>;
}
