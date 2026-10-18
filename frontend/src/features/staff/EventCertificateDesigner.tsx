import { useEffect, useState } from "react";
import { Card, Skeleton } from "../../components/ui";
import { eventErrorText } from "./eventUi";
import { useUploadCertificateArtwork } from "./eventsCertificateDesignerApi";
import { LayerEditor } from "./eventCredentials/LayerEditor";
import { CertificateLibrary } from "./eventCredentials/CertificateLibrary";
import { useDesign, type DesignInput } from "./eventCredentials/api";
import { upgradeDocument } from "./eventCredentials/layout";
import { BulkCertificates } from "./eventCredentials/BulkCertificates";

export function EventCertificateDesigner({ makerspaceId, eventId }: { makerspaceId: number; eventId: number }) {
  const { query, save, preview } = useDesign(eventId);
  const upload = useUploadCertificateArtwork(eventId);
  const [draft, setDraft] = useState<DesignInput | null>(null);
  const [dirty, setDirty] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  useEffect(() => {
    if (query.data && !dirty) setDraft({ parameters: upgradeDocument(query.data.parameters), artwork_id: query.data.artwork_id });
  }, [query.data, dirty]);
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  const pending = save.isPending || preview.isPending || upload.isPending;
  const error = query.error || save.error || preview.error || upload.error;
  return <section className="grid gap-4" aria-label="Certificate designer">
    <p className="text-sm text-muted">Each save creates an immutable revision. Existing certificates keep their original layout and artwork. Public verification reveals only the event, date and valid or revoked status.</p>
    {query.isLoading ? <div role="status"><span className="sr-only">Loading certificate template?</span><Skeleton className="h-48 w-full" /></div> : null}
    {query.isError ? <button className="desk-button" type="button" onClick={() => { void query.refetch(); }}>Retry certificate template</button> : null}
    {draft ? <Card><div className="grid gap-4">
      <p className="text-sm text-muted">{query.data?.id ? `Saved revision ${query.data.id}` : "Default certificate layout"}. Preview always uses a sample recipient.</p>
      <div className="grid grid-cols-2 gap-3">{(["page_width_mm", "page_height_mm"] as const).map((key) => <label className="grid gap-1 text-sm" key={key}>{key === "page_width_mm" ? "Width (mm)" : "Height (mm)"}<input type="number" className="desk-input" min={100} max={420} value={draft.parameters[key]} onChange={(event) => {
        setDirty(true); setDraft({ ...draft, parameters: { ...draft.parameters, [key]: Number(event.target.value) } });
      }} /></label>)}</div>
      <label className="grid gap-1 text-sm">Private logo or background (PNG/JPEG, up to 10 MB)<input className="desk-input" type="file" accept="image/png,image/jpeg" disabled={pending} onChange={(event) => {
        const file = event.target.files?.[0]; event.target.value = "";
        if (file) upload.mutate(file, { onSuccess: (artwork) => { setDirty(true); setDraft((current) => current ? { ...current, artwork_id: artwork.id } : current); } });
      }} /></label>
      <label className="grid gap-1 text-sm">Add a private image layer<input className="desk-input" type="file" accept="image/png,image/jpeg" disabled={pending || draft.parameters.layers.length >= 20} onChange={(event) => {
        const file = event.target.files?.[0]; event.target.value = "";
        if (file) upload.mutate(file, { onSuccess: (artwork) => {
          const resource = artwork as { id: number; resource_id: string };
          setDirty(true); setDraft((current) => current ? { ...current, parameters: { ...current.parameters,
            layers: [...current.parameters.layers, { id: crypto.randomUUID(), order: current.parameters.layers.length,
              type: "image", x_mm: 10, y_mm: 10, width_mm: 40, height_mm: 30, rotation: 0,
              resource_id: resource.resource_id }] } } : current);
        } });
      }} /></label>
      {draft.artwork_id ? <button className="desk-button" type="button" onClick={() => { setDirty(true); setDraft({ ...draft, artwork_id: null }); }}>Remove artwork from draft</button> : null}
      <LayerEditor document={draft.parameters} disabled={pending} onChange={(parameters) => { setDirty(true); setDraft({ ...draft, parameters }); }} />
      <div className="flex flex-wrap gap-2 border-t border-line pt-4">
        <button className="desk-button" type="button" disabled={pending} onClick={() => preview.mutate(draft, { onSuccess: (blob) => setPreviewUrl(URL.createObjectURL(blob)) })}>Preview certificate PDF</button>
        <button className="desk-button-primary" type="button" disabled={pending} onClick={() => save.mutate(draft, { onSuccess: () => setDirty(false) })}>Save new certificate revision</button>
      </div>
      {dirty ? <p role="status" className="text-sm text-warn-ink">Unsaved layout changes. A failed or stale save keeps this draft.</p> : null}
      {save.isSuccess ? <p role="status" className="text-sm text-success-ink">Certificate revision saved.</p> : null}
      <CertificateLibrary makerspaceId={makerspaceId} eventId={eventId} document={draft.parameters} eventVersion={query.data?.event_version} eventRevisionId={query.data?.id} />
    </div></Card> : null}
    {previewUrl ? <div className="grid gap-2"><iframe className="h-96 w-full rounded-control border border-line" src={previewUrl} title="Certificate PDF preview" /><button type="button" className="desk-button" onClick={() => setPreviewUrl(null)}>Close certificate preview</button></div> : null}
    {error ? <p role="alert" className="text-sm text-danger">{eventErrorText(error)}</p> : null}
    <BulkCertificates eventId={eventId} />
  </section>;
}
