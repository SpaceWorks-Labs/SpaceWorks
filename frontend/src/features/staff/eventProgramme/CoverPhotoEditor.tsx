import { t } from "@lingui/core/macro";
import { useCallback, useEffect, useRef, useState } from "react";
import { RotateCcw, Undo2 } from "lucide-react";
import { Card } from "../../../components/ui";
import { coverFileName, coverFileProblem, DEFAULT_COVER_EDITS, renderCover, type CoverEdits } from "./coverImage";
import { CoverCropStage } from "./CoverCropStage";
import { CoverAdjustControls, CoverCropControls } from "./CoverControls";
import { isProtectedDenial } from "./sessionScope";
import { LogoLoader } from "../../../components/LogoLoader";
import { BoxArt } from "../../../components/BoxSpinner";

type Props = {
  onSave: (file: File, altText: string) => Promise<void>;
  onPendingChange?: (pending: boolean) => void;
  title?: string;
  /** Ask for an image description (website images); event and series covers have none. */
  describe?: boolean;
  /** Start straight from a file the person already picked. */
  initialFile?: File | null;
  onCancel?: () => void;
};

/**
 * The full cover editor (parity E-F3, B4): crop to a shape with guides for every place the cover appears,
 * zoom, rotate, straighten, flip, a preset look and colour sliders, undo. The result is encoded as WebP
 * where the browser can, and the server re-encodes it to WebP and strips metadata either way.
 */
export function CoverPhotoEditor({ onSave, onPendingChange, title = t`Give the event a cover`, describe = true, initialFile = null, onCancel }: Props) {
  const [source, setSource] = useState<File | null>(null);
  const [src, setSrc] = useState("");
  const [natural, setNatural] = useState<{ width: number; height: number } | null>(null);
  const [edits, setEdits] = useState<CoverEdits>(DEFAULT_COVER_EDITS);
  const [history, setHistory] = useState<CoverEdits[]>([]);
  const [guides, setGuides] = useState(true);
  const [alt, setAlt] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const current = useRef(edits); current.current = edits;
  const choose = (file: File) => {
    const problem = coverFileProblem(file);
    if (problem) { setError(problem); return; }
    setError(""); setSource(file); setEdits(DEFAULT_COVER_EDITS); setHistory([]); setSaved(false); setNatural(null);
  };
  useEffect(() => { if (initialFile) choose(initialFile); }, [initialFile]);
  useEffect(() => {
    if (!source) { setSrc(""); return; }
    const url = URL.createObjectURL(source); setSrc(url);
    const image = new Image();
    image.onload = () => setNatural({ width: image.naturalWidth, height: image.naturalHeight });
    image.onerror = () => setError(t`This image could not be opened. Choose another file.`);
    image.src = url;
    return () => { image.onload = null; URL.revokeObjectURL(url); };
  }, [source]);
  useEffect(() => { onPendingChange?.(saving); return () => onPendingChange?.(false); }, [saving, onPendingChange]);

  const remember = useCallback(() => setHistory(rows => [...rows.slice(-29), current.current]), []);
  const live = useCallback((patch: Partial<CoverEdits>) => { setSaved(false); setEdits(value => ({ ...value, ...patch })); }, []);
  const update = (patch: Partial<CoverEdits>) => { remember(); live(patch); };
  const forget = () => { setSource(null); setNatural(null); setAlt(""); setHistory([]); setEdits(DEFAULT_COVER_EDITS); };
  const save = async () => {
    if (!source) return;
    setSaving(true); setError("");
    try {
      const blob = await renderCover(source, edits);
      await onSave(new File([blob], coverFileName(blob), { type: blob.type }), alt.trim());
      setSaved(true);
    } catch (reason) {
      if (isProtectedDenial(reason)) forget();
      setError(reason instanceof Error ? reason.message : t`Could not save the cover.`);
    } finally { setSaving(false); }
  };

  return <Card><section className="grid gap-5" aria-label={t`Cover photo editor`}>
    <h3 className="title-section">{title}</h3>
    <label className="grid gap-1 text-sm font-semibold">{source ? t`Choose a different image` : t`Image`}
      <input type="file" accept="image/jpeg,image/png,image/webp" className="desk-input font-normal" disabled={saving}
        onChange={event => { const file = event.target.files?.[0]; if (file) choose(file); event.target.value = ""; }} /></label>
    {source && natural ? <>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(16rem,2fr)]">
        <div className="grid content-start gap-3">
          <CoverCropStage src={src} natural={natural} edits={edits} guides={guides} onBegin={remember} onLive={live} />
          <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" className="h-5 w-5 accent-accent" checked={guides}
            onChange={event => setGuides(event.target.checked)} />{t`Show where cards and social previews crop the cover`}</label>
        </div>
        <div className="grid content-start gap-6">
          <CoverCropControls edits={edits} update={update} />
          <CoverAdjustControls edits={edits} update={update} />
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="desk-button" type="button" disabled={!history.length} onClick={() => { setEdits(history[history.length - 1]); setHistory(history.slice(0, -1)); setSaved(false); }}><Undo2 size={18} aria-hidden="true" />{t`Undo`}</button>
        <button className="desk-button" type="button" onClick={() => update(DEFAULT_COVER_EDITS)}><RotateCcw size={18} aria-hidden="true" />{t`Reset all`}</button>
      </div>
      {describe ? <label className="grid gap-1 text-sm">{t`Image description`}<input className="desk-input" maxLength={300} value={alt} onChange={event => setAlt(event.target.value)}
        placeholder={t`Describe the people, place or work shown`} /></label> : null}
    </> : source ? <LogoLoader label={t`Opening the image…`} size={48} className="min-h-16 py-3" /> : null}
    <div role="status" aria-live="polite" className="text-sm empty:hidden">{saving ? t`Saving cover…` : saved ? <span className="text-success-ink">{t`Cover saved.`}</span> : ""}</div>
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    <div className="flex flex-wrap justify-end gap-2">
      {onCancel ? <button className="desk-button" type="button" disabled={saving} onClick={onCancel}>{t`Cancel`}</button> : null}
      <button className="desk-button-primary" type="button" disabled={!source || !natural || saving} onClick={() => { void save(); }}>{saving ? <><BoxArt size={16} mono />{t`Saving cover…`}</> : t`Save cover`}</button>
    </div>
  </section></Card>;
}
