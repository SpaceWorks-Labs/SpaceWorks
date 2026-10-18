import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Printer, Upload, Download } from "lucide-react";
import { staffRequest, staffRequestBlob } from "../../../lib/api";
import { useBadgeDesignSave, useDeskPrint } from "./api";
import { STOCKS, safeDesignExport, type LayerDocument, type Stock } from "./layout";
import { LayerEditor } from "./LayerEditor";

type Seed = { seed_id: string; document: LayerDocument };
function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a");
  link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function DeskBadgePanel({ eventId, eventVersion, registrationIds, canEdit, canPrint }: {
  eventId: number; eventVersion?: number; registrationIds: number[]; canEdit: boolean; canPrint: boolean;
}) {
  const [stock, setStock] = useState<Stock>("cr80-landscape");
  const [theme, setTheme] = useState("light");
  const [document, setDocument] = useState<LayerDocument | null>(null);
  const [revision, setRevision] = useState<number | null>(null);
  const [includePhoto, setIncludePhoto] = useState(false);
  const [importError, setImportError] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [version, setVersion] = useState(eventVersion);
  const hydrated = useRef(false);
  const [showLogo, setShowLogo] = useState(true);
  const [failures, setFailures] = useState<{ registration_id: number; error_code: string }[]>([]);
  useEffect(() => { setVersion(eventVersion); }, [eventVersion]);
  const designs = useQuery({ queryKey: ["event-badge-designs", eventId, stock, theme], enabled: canEdit,
    queryFn: () => staffRequest<{ results: Seed[] }>(`/admin/events/${eventId}/badges/designs/?stock=${stock}&theme=${theme}`), retry: false });
  const save = useBadgeDesignSave(eventId);
  const print = useDeskPrint(eventId);
  const desk = useQuery({ queryKey: ["event-badge-desk-design", eventId], enabled: canPrint,
    queryFn: () => staffRequest<{ id: number; document: LayerDocument; stock: Stock; event_version: number }>(`/admin/events/${eventId}/badges/desk-design/`), retry: false });
  useEffect(() => { if (desk.data) setVersion(desk.data.event_version); if (desk.data && !hydrated.current) { hydrated.current = true; setDocument(desk.data.document); setRevision(desk.data.id); setStock(desk.data.stock); setVersion(desk.data.event_version); } }, [desk.data]);
  const testCard = useMutation({ mutationFn: () => staffRequestBlob(`/admin/events/${eventId}/badges/design-preview.pdf`, {
    method: "POST", body: JSON.stringify({ document, stock }),
  }), onSuccess: (blob) => setPreview(URL.createObjectURL(blob)) });
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const error = designs.error || save.error || print.error || testCard.error;
  const canGenerate = canPrint && Boolean(revision && version !== undefined && registrationIds.length);
  return <details className="my-3 rounded-control border border-line p-3"><summary className="min-h-11 cursor-pointer font-semibold text-ink">Desk ID cards with event check-in QR</summary>
    <p className="my-2 text-sm text-muted">Printing a QR replaces the old UUID ticket. Reprint the ticket or badge after replacement. Live badges stay private and are never attached to chat messages.</p>
    {canEdit ? <div className="grid gap-3">
      <label className="grid gap-1 text-sm">Card stock<select className="desk-input" value={stock} onChange={(event) => { setStock(event.target.value as Stock); setDocument(null); setRevision(null); }}>{Object.entries(STOCKS).map(([key, size]) => <option key={key} value={key}>{key} ({size.join(" × ")} mm)</option>)}</select></label>
      <label className="grid gap-1 text-sm">Design theme<select className="desk-input" value={theme} onChange={(event) => setTheme(event.target.value)}><option value="light">Light</option><option value="dark">Dark</option></select></label>
      <div className="flex flex-wrap gap-2">{designs.data?.results.map((seed) => <button className="desk-button" type="button" key={seed.seed_id} onClick={() => { setDocument(seed.document); setRevision(null); }}>{seed.seed_id.replace("badge-", "")}</button>)}</div>
      <label className="grid gap-1 text-sm"><span className="flex items-center gap-2"><Upload size={16} aria-hidden="true" />Import a person-free design</span><input className="desk-input" type="file" accept="application/json,.json" onChange={(event) => {
        const file = event.target.files?.[0]; event.target.value = "";
        if (!file) return;
        if (file.size > 65536) { setImportError("Design files must be at most 64 KB."); return; }
        void file.text().then((text) => { try {
          const parsed = JSON.parse(text) as LayerDocument;
          if (version === undefined) { setImportError("Refresh the event version before importing."); return; }
          save.mutate({ document: parsed, stock, expected_version: version }, { onSuccess: (value) => {
            setDocument(value.document); setRevision(value.id); setVersion(value.event_version); setImportError("");
          } });
        }
          catch { setImportError("Choose a valid JSON design."); } });
      }} /></label>
      {document ? <>
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={showLogo} onChange={(event) => { setShowLogo(event.target.checked); setRevision(null); }} />Include the makerspace logo</label>
        <LayerEditor kind="badge" document={document} onChange={(value) => { setDocument(value); setRevision(null); }} disabled={save.isPending} />
        <div className="flex flex-wrap gap-2"><button className="desk-button" type="button" disabled={save.isPending || version === undefined} onClick={() => { if (version !== undefined) save.mutate({ document: { ...document,
          layers: document.layers.filter((layer) => showLogo || layer.type !== "logo").map((layer, order) => ({ ...layer, order })) }, stock, expected_version: version }, { onSuccess: (value) => { setDocument(value.document); setRevision(value.id); setVersion(value.event_version); } }); }}>Validate and save design</button>
        <button className="desk-button" type="button" disabled={testCard.isPending} onClick={() => testCard.mutate()}>Print a sample card (dummy QR)</button>
        <button className="desk-button" type="button" disabled={revision === null} onClick={() => saveBlob(new Blob([safeDesignExport(document)], { type: "application/json" }), "badge-design.json")}><Download size={16} aria-hidden="true" />Export validated design</button></div>
      </> : null}
    </div> : <p className="text-sm text-muted">Your event manager selects the desk design. Check-in permission allows printing attended registrations.</p>}
    {canPrint ? <div className="mt-3 grid gap-3"><label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={includePhoto} onChange={(event) => setIncludePhoto(event.target.checked)} />Include selected photos where each member has given print consent</label>
      <button className="desk-button-primary" type="button" disabled={!canGenerate || print.isPending} onClick={() => {
        if (revision && version !== undefined) print.mutate({ registration_ids: registrationIds, expected_version: version,
          template_revision: revision, stock, include_photo: includePhoto }, { onSuccess: (result) => { setPreview(URL.createObjectURL(result.blob)); setFailures(result.failures); } });
      }}><Printer size={16} aria-hidden="true" />Prepare {registrationIds.length} ID cards</button></div> : null}
    {preview ? <><iframe src={preview} className="mt-3 h-96 w-full border border-line" title="Print-ready event ID cards" /><a className="desk-button mt-2" href={preview} download="event-id-cards.pdf">Download print PDF</a></> : null}
    {failures.length ? <p role="alert" className="mt-2 text-sm text-warn-ink">Cards were not printed for registrations {failures.map((row) => `#${row.registration_id}`).join(", ")}. Review their current eligibility before trying again.</p> : null}
    {error || importError ? <p role="alert" className="mt-2 text-sm text-danger">{importError || error?.message}</p> : null}
  </details>;
}
