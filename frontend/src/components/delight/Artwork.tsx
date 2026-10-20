import { useDelight, useReducedMotion, type DelightArtwork } from "./DelightProvider";
import "./delight.css";
import "./patch.css";

/** Artwork remains owned by ARTWORK. Never generate substitute programme illustrations. */
export function DelightArt({ name, className = "" }: { name: keyof DelightArtwork; className?: string }) {
  const { enabled, artwork } = useDelight();
  const reduced = useReducedMotion();
  const source = artwork[name];
  if (!enabled || !source) return null;
  // Patch uses one file in both themes (never recoloured); patch.css adds the dark-mode plate.
  if (source.patch) return <span aria-hidden="true" data-patch="" className={`sw-patch-plate pointer-events-none inline-flex items-center ${className}`}>
    {source.frames ? <span className={`sw-patch-sprite ${reduced ? "" : "sw-patch-stride"}`} style={{ backgroundImage: `url(${source.light})` }} />
      : <img alt="" src={reduced && source.still ? source.still : source.light} className="h-full w-full object-contain" draggable={false} />}
  </span>;
  return <span aria-hidden="true" className={`pointer-events-none inline-block ${className}`}>
    <img alt="" src={source.light} className="h-full w-full object-contain dark:hidden" draggable={false} />
    <img alt="" src={source.dark} className="hidden h-full w-full object-contain dark:block" draggable={false} />
  </span>;
}

export function BrandLoader({ label = "Loading" }: { label?: string }) {
  const { enabled } = useDelight();
  const reduced = useReducedMotion();
  return <div role="status" className="flex min-h-11 items-center justify-center gap-3 text-muted">
    <DelightArt name="loader" className={enabled && !reduced ? "sw-delight-loader h-10 w-10" : "h-10 w-10"} />
    <span>{label}</span>
  </div>;
}

export function MoodGlyph({ mood }: { mood: "welcome" | "success" | "waiting" | "empty" | "error" }) {
  return <DelightArt name={mood} className="sw-delight-glyph h-12 w-12" />;
}
