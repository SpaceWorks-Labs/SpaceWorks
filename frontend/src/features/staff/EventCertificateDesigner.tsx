import { t } from "@lingui/core/macro";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Card } from "../../components/ui";
import { eventErrorText } from "./eventUi";
import { certificateArtworkByResource, useUploadCertificateArtwork } from "./eventsCertificateDesignerApi";
import { CertificateStudio } from "./eventCredentials/CertificateStudio";
import { certificateStudioValues, compileCertificateV2, LEGACY_ARTWORK } from "./eventCredentials/certificateLayout";
import type { CardDocument } from "../../components/card-designer/cardTypes";
import type { StudioAssets } from "../../components/card-designer/studioAssets";
import { staffRequestBlob } from "../../lib/api";
import { CertificateLibrary } from "./eventCredentials/CertificateLibrary";
import { useDesign, type CertificateDesign } from "./eventCredentials/api";
import { upgradeDocument } from "./eventCredentials/layout";
import { SeedPicker } from "./eventCredentials/SeedPicker";
import { useQueryClient } from "@tanstack/react-query";
import { BulkCertificates } from "./eventCredentials/BulkCertificates";
import { SignatoriesPanel } from "./eventCredentials/SignatoriesPanel";
import { useSignatories } from "./eventCredentials/signatoryApi";
import { KindPicker, SampleName } from "./eventCredentials/designer/PageAndSample";
import { SIGNATURE_SAMPLES, type CertificateKind } from "./eventCredentials/designer/samples";
import { LogoLoader } from "../../components/LogoLoader";
import { BoxArt } from "../../components/BoxSpinner";

export function EventCertificateDesigner({ makerspaceId, eventId }: { makerspaceId: number; eventId: number }) {
  const [kind, setKind] = useState<CertificateKind | "">("");
  const { query, save, preview } = useDesign(eventId, kind);
  const upload = useUploadCertificateArtwork(eventId);
  const signatories = useSignatories(eventId);
  const client = useQueryClient();
  const [draft, setDraft] = useState<{ parameters: CardDocument; artwork_id: number | null } | null>(null);
  const [dirty, setDirty] = useState(false);
  const [sampleName, setSampleName] = useState("Priya Raman");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  useEffect(() => { setDirty(false); setDraft(null); }, [kind]);
  useEffect(() => {
    if (query.data && !dirty) setDraft({ parameters: toStudio(query.data), artwork_id: query.data.artwork_id });
  }, [query.data, dirty]);
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  const signatures = useMemo(() => Object.fromEntries([1, 2, 3].map((slot) => {
    const row = signatories.query.data?.signatories.find((item) => item.slot === slot);
    // A signatory whose approval is still pending prints nothing yet: the page says so instead of showing a clean name.
    const waiting = row && signatories.query.data?.approval_required
      && !signatories.query.data.designs.some((design) => design.slots.some((item) => item.slot === slot && item.approved));
    return [slot, row ? { name: waiting ? `${row.name} ${t`(awaiting approval)`}` : row.name, title: row.title } : SIGNATURE_SAMPLES[slot]];
  })), [signatories.query.data]);
  const artworkId = useRef<number | null>(null);
  const knownArtwork = useRef(new Map<string, number>());
  artworkId.current = draft?.artwork_id ?? null;
  const assets = useMemo<StudioAssets>(() => ({
    upload: async (_kind, file) => {
      const artwork = await upload.mutateAsync(file) as { id: number; resource_id?: string };
      const assetId = artwork.resource_id ?? String(artwork.id);
      knownArtwork.current.set(assetId, artwork.id);
      return { asset_id: assetId, mean_colour: "#FFFFFF" };
    },
    load: async (assetId) => {
      const id = assetId === LEGACY_ARTWORK ? artworkId.current : knownArtwork.current.get(assetId) ?? null;
      // A layer saved earlier holds only the resource UUID: resolve it on the server inside this event.
      if (id === null) return URL.createObjectURL(await certificateArtworkByResource(eventId, assetId));
      return URL.createObjectURL(await staffRequestBlob(`/admin/events/${eventId}/certificate-artwork/${id}/`));
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps -- the upload mutation object changes every render; mutateAsync is stable
  }), [eventId]);
  const pending = save.isPending || preview.isPending || upload.isPending;
  const error = query.error || save.error || preview.error || upload.error;
  const edit = (next: { parameters: CardDocument; artwork_id: number | null }) => { setDirty(true); setDraft(next); };
  const studioChange = useCallback((parameters: CardDocument) => { setDirty(true); setDraft((current) => current ? { ...current, parameters } : current); }, []);
  return <section className="grid gap-4" aria-label={t`Certificate designer`}>
    <p className="text-sm text-muted">{t`Each save creates a new revision; certificates already issued keep the design they were issued with. Public verification shows only what the certificate's verification settings allow.`}</p>
    <KindPicker value={kind} onChange={(value) => { if (!dirty || window.confirm(t`Discard unsaved changes to this design?`)) setKind(value); }}
      ownDesigns={query.data?.own_designs ?? []} usesDefault={Boolean(query.data?.uses_default)} />
    {query.isLoading ? <div role="status"><span className="sr-only">{t`Loading the certificate design…`}</span><LogoLoader size={48} className="min-h-48 py-3" /></div> : null}
    {query.isError ? <button className="desk-button" type="button" onClick={() => { void query.refetch(); }}>{t`Retry loading the design`}</button> : null}
    <SeedPicker eventId={eventId} version={query.data?.event_version} kind="certificate" onInstall={(value) => {
      setDraft({ parameters: compileCertificateV2(value.document), artwork_id: null }); setDirty(false);
      void client.invalidateQueries({ queryKey: ["events", "credentials", eventId] });
    }} />
    {draft ? <Card><div className="grid gap-5">
      <p className="text-sm text-muted">{query.data?.uses_default ? t`Starting from the default design.` : query.data?.id ? t`Saved revision ${query.data.id}.` : t`Starter layout.`} {t` The preview prints a sample recipient.`}</p>
      {draft.artwork_id ? <button className="desk-button justify-self-start" type="button" onClick={() => edit({ ...draft, artwork_id: null })}>{t`Remove artwork from this design`}</button> : null}
      <SampleName value={sampleName} onChange={setSampleName} />
      <CertificateStudio document={draft.parameters} disabled={pending} onChange={studioChange} assets={assets} makerspaceId={makerspaceId}
        values={certificateStudioValues(sampleName || "Priya Raman", kind, signatures)} />
      <div className="flex flex-wrap gap-2 border-t border-line pt-4">
        <button className="desk-button" type="button" disabled={pending} onClick={() => preview.mutate({ ...draft, parameters: asV3(draft.parameters), sample_name: sampleName },
          { onSuccess: (blob) => setPreviewUrl(URL.createObjectURL(blob)) })}>{preview.isPending ? <><BoxArt size={16} mono />{t`Rendering preview…`}</> : t`Preview exact PDF`}</button>
        <button className="desk-button-primary" type="button" disabled={pending} onClick={() => save.mutate({ ...draft, parameters: asV3(draft.parameters) }, { onSuccess: () => setDirty(false) })}>
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

const asV3 = (document: CardDocument): CardDocument => ({ ...document, version: 3, kind: "certificate" });

/** A stored revision as a Studio document: v3 as is; v2 (and the old v1 name box) compiled, never rewritten until saved. */
function toStudio(design: CertificateDesign): CardDocument {
  const parameters = design.parameters;
  if (parameters.version === 3) return parameters as CardDocument;
  return compileCertificateV2(upgradeDocument(parameters as Parameters<typeof upgradeDocument>[0]), design.artwork_id !== null);
}
