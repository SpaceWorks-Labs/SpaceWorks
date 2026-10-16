import { useEffect, useState } from "react";

import { PositionedLayoutEditor } from "../../components/print-layout/PositionedLayoutEditor";
import { layoutFits } from "../../components/print-layout/positionedLayout";
import { eventErrorText } from "./eventUi";
import {
  type CertificateTemplateInput, useEventCertificateTemplate, usePreviewEventCertificate,
  useSaveEventCertificateTemplate, useUploadCertificateArtwork,
} from "./eventsCertificateDesignerApi";

export function EventCertificateDesigner({ makerspaceId, eventId }: { makerspaceId: number; eventId: number }) {
  const template = useEventCertificateTemplate(eventId);
  const save = useSaveEventCertificateTemplate(makerspaceId, eventId);
  const preview = usePreviewEventCertificate(eventId);
  const upload = useUploadCertificateArtwork(eventId);
  const [draft, setDraft] = useState<CertificateTemplateInput | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  useEffect(() => { if (template.data) setDraft({ parameters: template.data.parameters, artwork_id: template.data.artwork_id }); }, [template.data]);
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  const error = template.error || save.error || preview.error || upload.error;
  const pending = save.isPending || preview.isPending || upload.isPending;
  const fits = draft && layoutFits([draft.parameters.name_box], draft.parameters.page_width_mm, draft.parameters.page_height_mm);
  return <section className="border-t border-line pt-5" aria-label="Certificate designer">
    <h3 className="title-section">Certificate designer</h3>
    <p className="mt-1 text-sm text-muted">Every save creates an immutable revision. Certificates already issued or awaiting rendering keep their original layout and artwork.</p>
    {template.isLoading ? <p className="mt-3 text-sm" role="status">Loading certificate template...</p> : null}
    {template.isError ? <button className="desk-button mt-2" type="button" onClick={() => { void template.refetch(); }}>Retry certificate template</button> : null}
    {draft ? <div className="mt-3 grid gap-3">
      <p className="text-xs text-muted">{template.data?.id ? `Saved revision ${template.data.id}` : "Default certificate layout"}. PDF preview uses a sample name.</p>
      <div className="grid grid-cols-2 gap-3">
        {([["page_width_mm", "Certificate width (mm)"], ["page_height_mm", "Certificate height (mm)"]] as const).map(([key, label]) =>
          <label className="grid gap-1 text-sm" key={key}>{label}<input className="desk-input" type="number" min="100" max="420" disabled={pending}
            value={draft.parameters[key]} onChange={(event) => {
              const value = Number(event.target.value); if (value >= 100 && value <= 420) setDraft({ ...draft, parameters: { ...draft.parameters, [key]: value } });
            }} /></label>)}
      </div>
      <label className="grid gap-1 text-sm">Private certificate artwork (PNG or JPEG, up to 10 MB)
        <input type="file" accept="image/png,image/jpeg" disabled={pending} onChange={(event) => {
          const file = event.target.files?.[0]; event.target.value = "";
          if (file) upload.mutate(file, { onSuccess: (artwork) => {
            setDraft((current) => current ? { ...current, artwork_id: artwork.id } : current);
            setPreviewUrl(null);
          } });
        }} />
      </label>
      {upload.isPending ? <p className="text-sm" role="status">Uploading and validating private artwork...</p> : null}
      {draft.artwork_id ? <div className="flex items-center gap-3"><p className="text-sm text-muted">Private artwork attached. Preview it in the PDF.</p><button className="desk-button" type="button" disabled={pending} onClick={() => setDraft({ ...draft, artwork_id: null })}>Remove artwork from draft</button></div> : null}
      <PositionedLayoutEditor widthMm={draft.parameters.page_width_mm} heightMm={draft.parameters.page_height_mm} gridMm={draft.parameters.grid_mm ?? 1}
        onGridChange={(grid_mm) => setDraft({ ...draft, parameters: { ...draft.parameters, grid_mm } })}
        elements={[draft.parameters.name_box]} labels={{ name: "Sample recipient name" }} disabled={pending}
        onChange={(elements) => setDraft({ ...draft, parameters: { ...draft.parameters, name_box: elements[0] } })} />
      <div className="flex flex-wrap gap-2">
        <button className="desk-button" type="button" disabled={pending || !fits} onClick={() => preview.mutate(draft, { onSuccess: (blob) => setPreviewUrl(URL.createObjectURL(blob)) })}>{preview.isPending ? "Rendering preview..." : "Preview certificate PDF"}</button>
        <button className="desk-button-primary" type="button" disabled={pending || !fits} onClick={() => save.mutate(draft)}>{save.isPending ? "Saving revision..." : "Save new certificate revision"}</button>
      </div>
      {save.isSuccess ? <p className="text-sm text-success" role="status">Certificate revision saved. Existing certificates keep their original design.</p> : null}
    </div> : null}
    {previewUrl ? <div className="mt-3"><iframe className="h-96 w-full border border-line" src={previewUrl} title="Certificate PDF preview" /><button className="desk-button mt-2" type="button" onClick={() => setPreviewUrl(null)}>Close certificate preview</button></div> : null}
    {error ? <p className="mt-2 text-sm text-danger" role="alert">{eventErrorText(error)}</p> : null}
  </section>;
}
