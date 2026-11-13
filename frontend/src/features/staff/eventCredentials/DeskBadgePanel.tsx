import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Printer, Upload, Download } from "lucide-react";
import { staffRequest, staffRequestBlob } from "../../../lib/api";
import { useBadgeDesignSave, useDeskPrint } from "./api";
import { type LayerDocument } from "./layout";
import { badgeDesignFile, blankBadge, CUSTOM_RANGE_MM, DESIGN_STOCKS, isSeedable, parseBadgeDesignFile, stockSize,
  validCustomSide, type DesignStock } from "./badgeStocks";
import { SeedPicker } from "./SeedPicker";
import { LayerEditor } from "./LayerEditor";

type Seed = { seed_id: string; document: LayerDocument };
function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a");
  link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function DeskBadgePanel({ eventId, eventVersion, registrationIds, canEdit, canPrint }: {
  eventId: number; eventVersion?: number; registrationIds: number[]; canEdit: boolean; canPrint: boolean;
}) {
  const [stock, setStock] = useState<DesignStock>("cr80-landscape");
  const [custom, setCustom] = useState({ width: 90, height: 60 });
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
  const designs = useQuery({ queryKey: ["event-badge-designs", eventId, stock, theme], enabled: canEdit && isSeedable(stock),
    queryFn: () => staffRequest<{ results: Seed[] }>(`/admin/events/${eventId}/badges/designs/?stock=${stock}&theme=${theme}`), retry: false });
  const save = useBadgeDesignSave(eventId);
  const print = useDeskPrint(eventId);
  const desk = useQuery({ queryKey: ["event-badge-desk-design", eventId], enabled: canPrint,
    queryFn: () => staffRequest<{ id: number; document: LayerDocument; stock: DesignStock; event_version: number }>(`/admin/events/${eventId}/badges/desk-design/`), retry: false });
  useEffect(() => { if (desk.data) setVersion(desk.data.event_version); if (desk.data && !hydrated.current) { hydrated.current = true; setDocument(desk.data.document); setRevision(desk.data.id); setStock(desk.data.stock); setVersion(desk.data.event_version);
    if (desk.data.stock === "custom") setCustom({ width: desk.data.document.page_width_mm, height: desk.data.document.page_height_mm }); } }, [desk.data]);
  const [width, height] = stockSize(stock, custom);
  const customValid = stock !== "custom" || (validCustomSide(custom.width) && validCustomSide(custom.height));
  const testCard = useMutation({ mutationFn: () => staffRequestBlob(`/admin/events/${eventId}/badges/design-preview.pdf`, {
    method: "POST", body: JSON.stringify({ document, stock }),
  }), onSuccess: (blob) => setPreview(URL.createObjectURL(blob)) });
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const error = designs.error || save.error || print.error || testCard.error;
  const canGenerate = canPrint && Boolean(revision && version !== undefined && registrationIds.length);
  return <details className="my-3 rounded-control border border-line p-3"><summary className="min-h-11 cursor-pointer font-semibold text-ink">{t`Desk ID cards with event check-in QR`}</summary>
    <p className="my-2 text-sm text-muted">{t`Printing a QR replaces the old UUID ticket. Reprint the ticket or badge after replacement. Live badges stay private and are never attached to chat messages.`}</p>
    {canEdit ? <div className="grid gap-3">
      <label className="grid gap-1 text-sm">{t`Card stock`}<select className="desk-input" value={stock} onChange={(event) => { setStock(event.target.value as DesignStock); setDocument(null); setRevision(null); }}>{Object.entries(DESIGN_STOCKS).map(([key, size]) => <option key={key} value={key}>{key} ({size.join(" × ")} mm)</option>)}<option value="custom">{t`Custom size`}</option></select></label>
      {stock === "custom" ? <div className="grid gap-2 sm:grid-cols-2">{(["width", "height"] as const).map((side) => <label key={side} className="grid gap-1 text-sm">
        {side === "width" ? t`Width (mm)` : t`Height (mm)`}<input className="desk-input" type="number" min={CUSTOM_RANGE_MM[0]} max={CUSTOM_RANGE_MM[1]} step={0.1}
          value={custom[side]} onChange={(event) => { const next = { ...custom, [side]: Number(event.target.value) }; setCustom(next); setRevision(null);
            if (document) setDocument({ ...document, page_width_mm: next.width, page_height_mm: next.height }); }} /></label>)}
        {!customValid ? <p role="alert" className="text-sm text-danger sm:col-span-2">{t`Use ${CUSTOM_RANGE_MM[0]}–${CUSTOM_RANGE_MM[1]} mm on each side, in 0.1 mm steps.`}</p> : null}</div> : null}
      <label className="grid gap-1 text-sm">{t`Design theme`}<select className="desk-input" value={theme} onChange={(event) => setTheme(event.target.value)}><option value="light">{t`Light`}</option><option value="dark">{t`Dark`}</option></select></label>
      {isSeedable(stock) ? <SeedPicker eventId={eventId} version={version} kind="badge" stock={stock} onInstall={(value) => {
        setDocument(value.document); setRevision(value.id); setVersion(value.event_version);
      }} /> : <div className="flex flex-wrap items-center gap-2"><p className="text-sm text-muted">{t`There are no ready-made designs for this size.`}</p>
        <button className="desk-button" type="button" disabled={!customValid} onClick={() => { setDocument(blankBadge(width, height)); setRevision(null); }}>{t`Start a blank badge`}</button></div>}
      <label className="grid gap-1 text-sm"><span className="flex items-center gap-2"><Upload size={16} aria-hidden="true" />{t`Import a design file`}</span><input className="desk-input" type="file" accept="application/json,.json" onChange={(event) => {
        const file = event.target.files?.[0]; event.target.value = "";
        if (!file) return;
        if (file.size > 65536) { setImportError(t`Design files must be at most 64 KB.`); return; }
        void file.text().then((text) => { try {
          const parsed = parseBadgeDesignFile(text);
          if (version === undefined) { setImportError(t`Refresh the event version before importing.`); return; }
          const target = parsed.stock ?? stock;
          if (target === "custom") setCustom({ width: parsed.document.page_width_mm, height: parsed.document.page_height_mm });
          setStock(target);
          // The server validates the imported design against the stock before it is kept.
          save.mutate({ document: parsed.document, stock: target, expected_version: version }, { onSuccess: (value) => {
            setDocument(value.document); setRevision(value.id); setVersion(value.event_version); setImportError("");
          } });
        }
          catch (failure) { setImportError(failure instanceof Error ? failure.message : t`Choose a valid JSON design.`); } });
      }} /></label>
      {document ? <>
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={showLogo} onChange={(event) => { setShowLogo(event.target.checked); setRevision(null); }} />{t`Include the makerspace logo`}</label>
        <LayerEditor kind="badge" document={document} onChange={(value) => { setDocument(value); setRevision(null); }} disabled={save.isPending} />
        <div className="flex flex-wrap gap-2"><button className="desk-button" type="button" disabled={save.isPending || version === undefined || !customValid} onClick={() => { if (version !== undefined) save.mutate({ document: { ...document,
          layers: document.layers.filter((layer) => showLogo || layer.type !== "logo").map((layer, order) => ({ ...layer, order })) }, stock, expected_version: version }, { onSuccess: (value) => { setDocument(value.document); setRevision(value.id); setVersion(value.event_version); } }); }}>{t`Validate and save design`}</button>
        <button className="desk-button" type="button" disabled={testCard.isPending} onClick={() => testCard.mutate()}>{t`Print a sample card (dummy QR)`}</button>
        <button className="desk-button" type="button" disabled={revision === null} onClick={() => saveBlob(new Blob([badgeDesignFile(document, stock)], { type: "application/json" }), "badge-design.json")}><Download size={16} aria-hidden="true" />{t`Export design file`}</button></div>
      </> : null}
    </div> : <p className="text-sm text-muted">{t`Your event manager selects the desk design. Check-in permission allows printing attended registrations.`}</p>}
    {canPrint ? <div className="mt-3 grid gap-3"><label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={includePhoto} onChange={(event) => setIncludePhoto(event.target.checked)} />{t`Include selected photos where each member has given print consent`}</label>
      <button className="desk-button-primary" type="button" disabled={!canGenerate || print.isPending} onClick={() => {
        if (revision && version !== undefined) print.mutate({ registration_ids: registrationIds, expected_version: version,
          template_revision: revision, stock, include_photo: includePhoto }, { onSuccess: (result) => { setPreview(URL.createObjectURL(result.blob)); setFailures(result.failures); } });
      }}><Printer size={16} aria-hidden="true" />{t`Prepare ${registrationIds.length} ID cards`}</button></div> : null}
    {preview ? <><iframe src={preview} className="mt-3 h-96 w-full border border-line" title={t`Print-ready event ID cards`} /><a className="desk-button mt-2" href={preview} download="event-id-cards.pdf">{t`Download print PDF`}</a></> : null}
    {failures.length ? <p role="alert" className="mt-2 text-sm text-warn-ink">{t`Cards were not printed for registrations ${failures.map((row) => `#${row.registration_id}`).join(", ")}. Review their current eligibility before trying again.`}</p> : null}
    {error || importError ? <p role="alert" className="mt-2 text-sm text-danger">{importError || error?.message}</p> : null}
  </details>;
}
