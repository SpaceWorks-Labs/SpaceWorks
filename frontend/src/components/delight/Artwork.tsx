import { useDelight, useReducedMotion, type DelightArtwork } from "./DelightProvider";
import "./delight.css";

/** Artwork remains owned by ARTWORK. Never generate substitute programme illustrations. */
export function DelightArt({ name, className = "" }: { name: keyof DelightArtwork; className?: string }) {
  const { enabled, artwork } = useDelight();
  const source = artwork[name];
  if (!enabled || !source) return null;
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
