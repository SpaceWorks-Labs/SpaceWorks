import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { LayerDocument } from "./layout";
import type { CardDocument } from "../../../components/card-designer/cardTypes";

type Template = { id: number; name: string; version: number; archived: boolean };
type Upload = { id: number; upload_url: string; headers: Record<string, string> };

/**
 * Edit one makerspace library template: rename it and append the current draft layout as a new
 * revision (`PATCH …/event-certificate-library/{id}/`), optionally with background artwork the
 * template owns (reserve → PUT to the staging key → finalize). Event copies keep their own revisions.
 */
export function CertificateLibraryEditor({ makerspaceId, templateId, document }: {
  makerspaceId: number; templateId: number; document: LayerDocument | CardDocument;
}) {
  const client = useQueryClient();
  const base = `/admin/makerspaces/${makerspaceId}/event-certificate-library/${templateId}/`;
  const listKey = ["event-certificate-library", makerspaceId];
  const detail = useQuery({ queryKey: [...listKey, "detail", templateId], retry: false, queryFn: () => staffRequest<Template>(base) });
  const [name, setName] = useState<string>();
  const [artwork, setArtwork] = useState<number | null>(null);
  const upload = useMutation({ mutationFn: async (file: File) => {
    if (!["image/png", "image/jpeg"].includes(file.type) || file.size < 1 || file.size > 10 * 1024 * 1024) {
      throw new Error(t`Choose a PNG or JPEG image up to 10 MB.`);
    }
    const reserved = await staffRequest<Upload>(`${base}artwork/`, { method: "POST",
      body: JSON.stringify({ content_type: file.type, content_length: file.size }) });
    const response = await fetch(reserved.upload_url, { method: "PUT", headers: reserved.headers, body: file });
    if (!response.ok) throw new Error(t`Artwork upload failed. Select the image to try again.`);
    return staffRequest<{ id: number; resource_id: string }>(`${base}artwork/${reserved.id}/finalize/`, { method: "POST", body: JSON.stringify({}) });
  }, onSuccess: (row) => setArtwork(row.id) });
  const save = useMutation({ mutationFn: () => staffRequest(base, { method: "PATCH", body: JSON.stringify({
    operation_id: crypto.randomUUID(), expected_version: detail.data?.version, name: (name ?? detail.data?.name ?? "").trim(),
    parameters: document, artwork_id: artwork,
  }) }), onSuccess: () => { setArtwork(null); void client.invalidateQueries({ queryKey: listKey }); } });
  if (detail.isLoading) return <LogoLoader label={t`Loading template…`} />;
  if (!detail.data) return detail.error ? <p role="alert" className="text-sm text-danger">{detail.error.message}</p> : null;
  const value = name ?? detail.data.name;
  const error = upload.error || save.error;
  return <fieldset className="grid gap-3 rounded-control border border-line p-3" disabled={detail.data.archived}>
    <legend className="px-1 text-sm font-semibold text-ink">{t`Edit library template`}</legend>
    {detail.data.archived ? <p className="text-sm text-muted">{t`This template is archived and read-only.`}</p> : null}
    <label className="grid gap-1 text-sm">{t`Library template name`}<input className="desk-input" maxLength={120} value={value} onChange={(event) => setName(event.target.value)} /></label>
    <label className="grid gap-1 text-sm">{t`Background artwork for this template`}
      <input className="desk-input" type="file" accept="image/png,image/jpeg" disabled={upload.isPending}
        onChange={(event) => { const file = event.target.files?.[0]; if (file) upload.mutate(file); event.target.value = ""; }} /></label>
    {upload.isPending ? <p role="status" className="text-sm text-muted">{t`Uploading artwork…`}</p> : null}
    {artwork ? <p role="status" className="text-sm text-muted">{t`Artwork ready. It is used when you save the next revision.`}</p> : null}
    <button type="button" className="desk-button justify-self-start" disabled={!value.trim() || save.isPending || upload.isPending} onClick={() => save.mutate()}>
      {t`Save draft layout as a new template revision`}</button>
    {save.isSuccess ? <p role="status" className="text-sm text-success-ink">{t`Template updated. Earlier revisions and event copies are unchanged.`}</p> : null}
    {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
  </fieldset>;
}
