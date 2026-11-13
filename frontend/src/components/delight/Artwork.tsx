import { t } from "@lingui/core/macro";
import { LogoLoader } from "../LogoLoader";
import { useDelight, type DelightArtwork } from "./DelightProvider";
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

/** One loader implementation: the Space Works box-opening animation (see `LogoLoader`). */
export function BrandLoader({ label = t`Loading` }: { label?: string }) {
  return <LogoLoader label={label} size={48} className="min-h-16 py-3" />;
}

export function MoodGlyph({ mood }: { mood: "welcome" | "success" | "waiting" | "empty" | "error" }) {
  return <DelightArt name={mood} className="sw-delight-glyph h-12 w-12" />;
}
