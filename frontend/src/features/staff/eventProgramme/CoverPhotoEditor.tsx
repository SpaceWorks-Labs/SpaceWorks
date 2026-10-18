import { useEffect, useState } from "react";
import { RotateCcw, Undo2 } from "lucide-react";
import { Card } from "../../../components/ui";
import { DEFAULT_COVER_EDITS, renderCover, type CoverEdits } from "./coverImage";
import { isProtectedDenial } from "./sessionScope";

export function CoverPhotoEditor({ onSave, onPendingChange }: { onSave: (file: File, altText: string) => Promise<void>; onPendingChange?: (pending: boolean) => void }) {
  const [source, setSource] = useState<File | null>(null);
  const [edits, setEdits] = useState<CoverEdits>(DEFAULT_COVER_EDITS);
  const [history, setHistory] = useState<CoverEdits[]>([]);
  const [rendered, setRendered] = useState<Blob | null>(null);
  const [preview, setPreview] = useState("");
  const [alt, setAlt] = useState("");
  const [working, setWorking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (!source) return;
    let active = true; setWorking(true); setRendered(null); setError("");
    const timer = setTimeout(() => { void renderCover(source, edits).then(blob => { if (active) setRendered(blob); }).catch(reason => { if (active) setError(reason instanceof Error ? reason.message : "Could not prepare the cover."); }).finally(() => { if (active) setWorking(false); }); }, 120);
    return () => { active = false; clearTimeout(timer); };
  }, [source, edits]);
  useEffect(() => { if (!rendered) { setPreview(""); return; } const url = URL.createObjectURL(rendered); setPreview(url); return () => URL.revokeObjectURL(url); }, [rendered]);
  useEffect(() => { onPendingChange?.(working || saving); return () => onPendingChange?.(false); }, [working, saving, onPendingChange]);
  const update = (patch: Partial<CoverEdits>) => { setHistory([...history.slice(-19), edits]); setEdits({ ...edits, ...patch }); setSaved(false); };
  return <Card><section className="grid gap-4" aria-label="Cover photo editor"><h3 className="title-section">Give the event a cover</h3>
    <label className="grid gap-1 text-sm font-semibold">Image<input type="file" accept="image/jpeg,image/png,image/webp" className="desk-input" onChange={e => { const file = e.target.files?.[0]; if (file) { setSource(file); setHistory([]); setEdits(DEFAULT_COVER_EDITS); setSaved(false); } }} /></label>
    <label className="grid gap-1 text-sm">Crop ratio<select className="desk-input" value={edits.ratio} onChange={e => update({ ratio: e.target.value as CoverEdits["ratio"] })}>{["16:7", "16:9", "1:1"].map(ratio => <option key={ratio}>{ratio}</option>)}</select></label>
    <div className="grid gap-3 sm:grid-cols-2">{([
      ["rotation", "Rotate", -180, 180, 1], ["straighten", "Straighten", -15, 15, 0.1], ["brightness", "Brightness (%)", 50, 150, 1], ["contrast", "Contrast (%)", 50, 150, 1], ["x", "Horizontal crop (%)", 0, 100, 1], ["y", "Vertical crop (%)", 0, 100, 1], ["zoom", "Zoom", 1, 3, 0.1],
    ] as const).map(([key, label, min, max, step]) => <label key={key} className="grid gap-1 text-sm">{label}<input type="number" className="desk-input" min={min} max={max} step={step} value={edits[key]} onChange={e => { const next = Number(e.target.value); if (Number.isFinite(next) && next >= min && next <= max) update({ [key]: next }); }} /></label>)}</div>
    <div className="flex flex-wrap gap-2"><button className="desk-button" type="button" disabled={!history.length} onClick={() => { setEdits(history[history.length - 1]); setHistory(history.slice(0, -1)); }}><Undo2 size={20} aria-hidden="true" />Undo</button><button className="desk-button" type="button" onClick={() => update(DEFAULT_COVER_EDITS)}><RotateCcw size={20} aria-hidden="true" />Reset</button></div>
    <label className="grid gap-1 text-sm">Image description<input className="desk-input" maxLength={300} value={alt} onChange={e => setAlt(e.target.value)} placeholder="Describe the people, place or work shown" /></label>
    {preview ? <div className="grid gap-4 sm:grid-cols-2"><figure><img className="w-full rounded-xl object-cover" src={preview} alt={alt || "Cover preview"} /><figcaption className="mt-1 text-xs text-muted">Event card preview</figcaption></figure><figure><img className="aspect-[1.91] w-full rounded-xl object-cover" src={preview} alt={alt || "Social cover preview"} /><figcaption className="mt-1 text-xs text-muted">Social crop preview</figcaption></figure></div> : null}
    {working ? <p role="status" className="text-sm">Preparing preview…</p> : null}{error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}{saved ? <p role="status" className="text-sm text-success">Cover saved.</p> : null}
    <button className="desk-button-primary justify-self-end" type="button" disabled={!rendered || working || saving} onClick={async () => { if (!rendered) return; setSaving(true); setError(""); try { await onSave(new File([rendered], "event-cover.jpg", { type: "image/jpeg" }), alt.trim()); setSaved(true); } catch (reason) { if (isProtectedDenial(reason)) { setSource(null); setRendered(null); setPreview(""); setAlt(""); setHistory([]); } setError(reason instanceof Error ? reason.message : "Could not save the cover."); } finally { setSaving(false); } }}>{saving ? "Saving cover…" : "Save cover"}</button>
  </section></Card>;
}
