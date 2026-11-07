import { t } from "@lingui/core/macro";
import { useEffect, useMemo, useState } from "react";
import { Card, Skeleton } from "../../components/ui";
import { eventErrorText } from "./eventUi";
import { useUploadCertificateArtwork } from "./eventsCertificateDesignerApi";
import { LayerEditor } from "./eventCredentials/LayerEditor";
import { CertificateLibrary } from "./eventCredentials/CertificateLibrary";
import { useDesign, type DesignInput } from "./eventCredentials/api";
import { upgradeDocument } from "./eventCredentials/layout";
import { SeedPicker } from "./eventCredentials/SeedPicker";
import { useQueryClient } from "@tanstack/react-query";
import { BulkCertificates } from "./eventCredentials/BulkCertificates";
import { SignatoriesPanel } from "./eventCredentials/SignatoriesPanel";
import { useSignatories } from "./eventCredentials/signatoryApi";
import { KindPicker, PageSizeFields, SampleName } from "./eventCredentials/designer/PageAndSample";
import { SIGNATURE_SAMPLES, certificateSampleValues, type CertificateKind } from "./eventCredentials/designer/samples";

export function EventCertificateDesigner({ makerspaceId, eventId }: { makerspaceId: number; eventId: number }) {
  const [kind, setKind] = useState<CertificateKind | "">("");
  const { query, save, preview } = useDesign(eventId, kind);
  const upload = useUploadCertificateArtwork(eventId);
  const signatories = useSignatories(eventId);
  const client = useQueryClient();
  const [draft, setDraft] = useState<DesignInput | null>(null);
  const [dirty, setDirty] = useState(false);
  const [sampleName, setSampleName] = useState("Priya Raman");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  useEffect(() => { setDirty(false); setDraft(null); }, [kind]);
  useEffect(() => {
    if (query.data && !dirty) setDraft({ parameters: upgradeDocument(query.data.parameters), artwork_id: query.data.artwork_id });
  }, [query.data, dirty]);
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  const signatures = useMemo(() => Object.fromEntries([1, 2, 3].map((slot) => {
    const row = signatories.query.data?.signatories.find((item) => item.slot === slot);
    return [slot, row ? { name: row.name, title: row.title } : SIGNATURE_SAMPLES[slot]];
  })), [signatories.query.data]);
  const pending = save.isPending || preview.isPending || upload.isPending;
  const error = query.error || save.error || preview.error || upload.error;
  const edit = (next: DesignInput) => { setDirty(true); setDraft(next); };
  return <section className="grid gap-4" aria-label={t`Certificate designer`}>
    <p className="text-sm text-muted">{t`Each save creates a new revision; certificates already issued keep the design they were issued with. Public verification shows only what the certificate's verification settings allow.`}</p>
    <KindPicker value={kind} onChange={(value) => { if (!dirty || window.confirm(t`Discard unsaved changes to this design?`)) setKind(value); }}
      ownDesigns={query.data?.own_designs ?? []} usesDefault={Boolean(query.data?.uses_default)} />
    {query.isLoading ? <div role="status"><span className="sr-only">{t`Loading the certificate design…`}</span><Skeleton className="h-48 w-full" /></div> : null}
    {query.isError ? <button className="desk-button" type="button" onClick={() => { void query.refetch(); }}>{t`Retry loading the design`}</button> : null}
    <SeedPicker eventId={eventId} version={query.data?.event_version} kind="certificate" onInstall={(value) => {
      setDraft({ parameters: value.document, artwork_id: null }); setDirty(false);
      void client.invalidateQueries({ queryKey: ["events", "credentials", eventId] });
    }} />
    {draft ? <Card><div className="grid gap-5">
      <p className="text-sm text-muted">{query.data?.uses_default ? t`Starting from the default design.` : query.data?.id ? t`Saved revision ${query.data.id}.` : t`Starter layout.`} {t` The preview prints a sample recipient.`}</p>
      <PageSizeFields document={draft.parameters} onChange={(parameters) => edit({ ...draft, parameters })} />
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-sm">{t`Background or logo artwork (PNG or JPEG, up to 10 MB)`}<input className="desk-input" type="file" accept="image/png,image/jpeg" disabled={pending} onChange={(event) => {
          const file = event.target.files?.[0]; event.target.value = "";
          if (file) upload.mutate(file, { onSuccess: (artwork) => { setDirty(true); setDraft((current) => current ? { ...current, artwork_id: artwork.id } : current); } });
        }} /></label>
        <label className="grid gap-1 text-sm">{t`Add a picture layer`}<input className="desk-input" type="file" accept="image/png,image/jpeg" disabled={pending || draft.parameters.layers.length >= 20} onChange={(event) => {
          const file = event.target.files?.[0]; event.target.value = "";
          if (file) upload.mutate(file, { onSuccess: (artwork) => {
            const resource = artwork as { id: number; resource_id: string };
            setDirty(true); setDraft((current) => current ? { ...current, parameters: { ...current.parameters,
              layers: [...current.parameters.layers, { id: crypto.randomUUID(), order: current.parameters.layers.length,
                type: "image", x_mm: 10, y_mm: 10, width_mm: 40, height_mm: 30, rotation: 0, resource_id: resource.resource_id }] } } : current);
          } });
        }} /></label>
      </div>
      {draft.artwork_id ? <button className="desk-button justify-self-start" type="button" onClick={() => edit({ ...draft, artwork_id: null })}>{t`Remove artwork from this design`}</button> : null}
      <SampleName value={sampleName} onChange={setSampleName} />
      <LayerEditor document={draft.parameters} disabled={pending} values={certificateSampleValues(sampleName || "Priya Raman", kind)}
        signatures={signatures} onChange={(parameters) => edit({ ...draft, parameters })} />
      <div className="flex flex-wrap gap-2 border-t border-line pt-4">
        <button className="desk-button" type="button" disabled={pending} onClick={() => preview.mutate({ ...draft, sample_name: sampleName },
          { onSuccess: (blob) => setPreviewUrl(URL.createObjectURL(blob)) })}>{preview.isPending ? t`Rendering preview…` : t`Preview exact PDF`}</button>
        <button className="desk-button-primary" type="button" disabled={pending} onClick={() => save.mutate(draft, { onSuccess: () => setDirty(false) })}>
          {kind ? t`Save this kind's design` : t`Save the default design`}</button>
      </div>
      {dirty ? <p role="status" className="text-sm text-warn-ink">{t`Unsaved changes. A failed save keeps this draft.`}</p> : null}
      {save.isSuccess && !dirty ? <p role="status" className="text-sm text-success-ink">{t`Design saved.`}</p> : null}
      <CertificateLibrary makerspaceId={makerspaceId} eventId={eventId} document={draft.parameters} eventVersion={query.data?.event_version} eventRevisionId={query.data?.id} />
    </div></Card> : null}
    {previewUrl ? <div className="grid gap-2"><iframe className="h-[32rem] w-full rounded-control border border-line" src={previewUrl} title={t`Certificate PDF preview`} />
      <button type="button" className="desk-button justify-self-start" onClick={() => setPreviewUrl(null)}>{t`Close the preview`}</button></div> : null}
    {error ? <p role="alert" className="text-sm text-danger">{eventErrorText(error)}</p> : null}
    <SignatoriesPanel eventId={eventId} />
    <BulkCertificates eventId={eventId} />
  </section>;
}
