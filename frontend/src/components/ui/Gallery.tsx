import { useState, type KeyboardEvent } from "react";
import { ChevronLeft, ChevronRight, Images } from "lucide-react";

import { Modal } from "./Modal";

export type GalleryPhoto = { id: number; url: string; caption?: string };

export type GalleryProps = {
  photos: GalleryPhoto[];
  /** Accessible name of the gallery, e.g. "Photos of Meeting room A". */
  label: string;
  /** Optional visible heading rendered above the photos. */
  title?: string;
  /** Shown instead of the gallery when there are no photos; omit to render nothing. */
  emptyMessage?: string;
  className?: string;
};

/**
 * Read-only place photo gallery shared by booking pages and the event "Hosted at" block.
 * One lead photo plus a thumbnail strip; any photo opens a keyboard-navigable viewer.
 */
export function Gallery({ photos, label, title, emptyMessage, className = "" }: GalleryProps) {
  const [open, setOpen] = useState<number | null>(null);
  if (!photos.length) {
    return emptyMessage ? <p className={`text-sm text-muted ${className}`}>{emptyMessage}</p> : null;
  }
  const [lead, ...rest] = photos;
  const thumbs = rest.slice(0, 4);
  const hidden = photos.length - 1 - thumbs.length;
  return (
    <section aria-label={label} className={`grid gap-3 ${className}`}>
      {title ? <h2 className="title-panel">{title}</h2> : null}
      <div className={`grid gap-2 ${thumbs.length ? "sm:grid-cols-[2fr_1fr]" : ""}`}>
        <PhotoButton photo={lead} index={0} count={photos.length} onOpen={setOpen} large />
        {thumbs.length ? (
          <ul className="grid grid-cols-4 gap-2 sm:grid-cols-2" aria-label="More photos">
            {thumbs.map((photo, offset) => (
              <li key={photo.id} className="relative">
                <PhotoButton photo={photo} index={offset + 1} count={photos.length} onOpen={setOpen} />
                {hidden > 0 && offset === thumbs.length - 1 ? (
                  <span aria-hidden="true" className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-lg bg-black/55 text-sm font-semibold text-white">
                    +{hidden}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <GalleryViewer photos={photos} index={open} onIndex={setOpen} label={label} />
    </section>
  );
}

function PhotoButton({ photo, index, count, onOpen, large = false }: {
  photo: GalleryPhoto; index: number; count: number; onOpen: (index: number) => void; large?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const name = photo.caption || `Photo ${index + 1} of ${count}`;
  return (
    <button type="button" onClick={() => onOpen(index)} aria-label={`Open ${name}`}
      className={`group block w-full overflow-hidden rounded-lg border border-line bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 ${large ? "aspect-[4/3] sm:aspect-auto sm:h-full sm:min-h-64" : "aspect-square"}`}>
      {failed ? (
        <span className="flex h-full w-full items-center justify-center text-muted"><Images aria-hidden="true" size={24} /></span>
      ) : (
        <img src={photo.url} alt={photo.caption ?? ""} loading="lazy" onError={() => setFailed(true)}
          className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.02] motion-reduce:transition-none" />
      )}
    </button>
  );
}

export function GalleryViewer({ photos, index, onIndex, label }: {
  photos: GalleryPhoto[]; index: number | null; onIndex: (index: number | null) => void; label: string;
}) {
  const photo = index === null ? undefined : photos[index];
  const step = (delta: number) => index !== null && onIndex((index + delta + photos.length) % photos.length);
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowRight") { event.preventDefault(); step(1); }
    if (event.key === "ArrowLeft") { event.preventDefault(); step(-1); }
  };
  return (
    <Modal open={photo !== undefined} onClose={() => onIndex(null)} size="xl"
      title={photo ? `${label} — ${(index ?? 0) + 1} of ${photos.length}` : label}>
      {photo ? (
        <div className="grid gap-3" onKeyDown={onKeyDown}>
          <img src={photo.url} alt={photo.caption ?? ""} className="max-h-[70vh] w-full rounded-lg bg-surface object-contain" />
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="desk-button min-h-11" onClick={() => step(-1)} disabled={photos.length < 2}>
              <ChevronLeft aria-hidden="true" size={20} /> Previous
            </button>
            <p className="min-w-0 flex-1 text-center text-sm text-muted">{photo.caption}</p>
            <button type="button" className="desk-button min-h-11" onClick={() => step(1)} disabled={photos.length < 2}>
              Next <ChevronRight aria-hidden="true" size={20} />
            </button>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
