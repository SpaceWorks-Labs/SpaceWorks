import { useId, useRef, useState } from "react";
import { ArrowDown, ArrowUp, ImagePlus, Trash2 } from "lucide-react";

import { ConfirmDialog } from "./ConfirmDialog";
import { ErrorText } from "./ErrorText";
import { GALLERY_ACCEPT } from "./galleryUpload";
import type { GalleryPhoto } from "./Gallery";

export type GalleryEditorProps = {
  photos: GalleryPhoto[];
  maxPhotos: number;
  /** False renders the photos read-only with the reason in `readOnlyMessage`. */
  canEdit: boolean;
  readOnlyMessage?: string;
  onUpload: (file: File) => Promise<unknown>;
  onCaption: (id: number, caption: string) => Promise<unknown>;
  /** Receives the complete new order of photo ids. */
  onReorder: (order: number[]) => Promise<unknown>;
  onRemove: (id: number) => Promise<unknown>;
};

/** Staff editor for an ordered place photo gallery: upload, caption, reorder, remove. */
export function GalleryEditor({ photos, maxPhotos, canEdit, readOnlyMessage, onUpload, onCaption, onReorder, onRemove }: GalleryEditorProps) {
  const inputId = useId();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [removing, setRemoving] = useState<GalleryPhoto | null>(null);
  const run = async (work: () => Promise<unknown>) => {
    setBusy(true); setError(undefined);
    try { await work(); } catch (caught) { setError(caught instanceof Error ? caught.message : "That change could not be saved."); }
    finally { setBusy(false); }
  };
  const move = (index: number, delta: number) => {
    const order = photos.map(photo => photo.id);
    const [moved] = order.splice(index, 1);
    order.splice(index + delta, 0, moved);
    return run(() => onReorder(order));
  };
  const full = photos.length >= maxPhotos;
  return (
    <section className="grid gap-4" aria-labelledby={`${inputId}-title`} aria-busy={busy}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 id={`${inputId}-title`} className="title-panel">Place photos</h3>
          <p className="mt-1 text-sm text-muted">
            Shown on the public and member booking pages and on events hosted here. {photos.length} of {maxPhotos} used.
          </p>
        </div>
        {canEdit ? (
          <>
            <input ref={input} id={inputId} type="file" accept={GALLERY_ACCEPT} className="sr-only" disabled={busy || full}
              onChange={event => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void run(() => onUpload(file)); }} />
            <button type="button" className="desk-button min-h-11" disabled={busy || full} onClick={() => input.current?.click()}>
              <ImagePlus aria-hidden="true" size={20} /> {busy ? "Saving…" : full ? "Gallery full" : "Add photo"}
            </button>
          </>
        ) : null}
      </div>
      {!canEdit && readOnlyMessage ? <p className="text-sm text-muted">{readOnlyMessage}</p> : null}
      <ErrorText message={error} />
      {photos.length ? (
        <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {photos.map((photo, index) => (
            <li key={photo.id} className="grid gap-2 rounded-xl border border-line bg-panel p-3">
              <img src={photo.url} alt={photo.caption ?? ""} className="aspect-[4/3] w-full rounded-lg bg-surface object-cover" />
              <CaptionField photo={photo} index={index} disabled={!canEdit || busy} onSave={caption => run(() => onCaption(photo.id, caption))} />
              {canEdit ? (
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <button type="button" className="desk-button min-h-11 min-w-11 justify-center px-2" aria-label={`Move photo ${index + 1} earlier`}
                    disabled={busy || index === 0} onClick={() => void move(index, -1)}><ArrowUp aria-hidden="true" size={18} /></button>
                  <button type="button" className="desk-button min-h-11 min-w-11 justify-center px-2" aria-label={`Move photo ${index + 1} later`}
                    disabled={busy || index === photos.length - 1} onClick={() => void move(index, 1)}><ArrowDown aria-hidden="true" size={18} /></button>
                  <button type="button" className="desk-button min-h-11" disabled={busy} onClick={() => setRemoving(photo)}>
                    <Trash2 aria-hidden="true" size={18} /> Remove
                  </button>
                </div>
              ) : null}
            </li>
          ))}
        </ol>
      ) : (
        <p className="rounded-xl border border-dashed border-line p-6 text-center text-sm text-muted">
          No photos yet.{canEdit ? " Add a few so people can see the place before they book." : ""}
        </p>
      )}
      <ConfirmDialog open={removing !== null} title="Remove photo" tone="danger" confirmLabel="Remove photo" pending={busy}
        message="The photo disappears from every booking and event page straight away."
        onCancel={() => setRemoving(null)}
        onConfirm={() => { const target = removing; setRemoving(null); if (target) void run(() => onRemove(target.id)); }} />
    </section>
  );
}

function CaptionField({ photo, index, disabled, onSave }: { photo: GalleryPhoto; index: number; disabled: boolean; onSave: (caption: string) => void }) {
  const [value, setValue] = useState(photo.caption ?? "");
  const id = useId();
  const dirty = value.trim() !== (photo.caption ?? "");
  return (
    <form className="grid gap-1" onSubmit={event => { event.preventDefault(); if (dirty) onSave(value); }}>
      <label htmlFor={id} className="text-sm">Caption for photo {index + 1}</label>
      <div className="flex gap-2">
        <input id={id} className="desk-input min-w-0 flex-1" maxLength={200} value={value} disabled={disabled}
          placeholder="What does this show?" onChange={event => setValue(event.target.value)} />
        {dirty ? <button type="submit" className="desk-button min-h-11" disabled={disabled}>Save</button> : null}
      </div>
    </form>
  );
}
