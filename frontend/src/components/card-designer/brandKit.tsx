// The brand kit (decision 344(b)): the space's own colours (from its theme, via GET .../brand-kit) first, then the
// SpaceWorks palette, offered as one-click swatches under every colour field of the studio. The server normalises
// the space colours to #RRGGBB and the swatch is applied through the same validated path as a typed colour.
import { useQuery } from "@tanstack/react-query";
import { t } from "@lingui/core/macro";
import { createContext, useContext, type ReactNode } from "react";

import { staffRequest } from "../../lib/api";
import { brandSwatches } from "./quickEdits";
import { rgbCss } from "./studioMath";

export type BrandKit = { colours: { label: string; hex: string }[]; logos: { source: string; label: string }[]; fonts: string[] };
export type Swatch = { label: string; hex: string };

const HEX = /^#[0-9A-F]{6}$/i;
const BrandContext = createContext<Swatch[] | null>(null);

export function useBrandKit(designId: number, enabled = true) {
  return useQuery({ queryKey: ["card-design-brand-kit", designId], enabled: enabled && designId > 0, staleTime: 5 * 60_000,
    queryFn: () => staffRequest<BrandKit>(`/admin/card-designs/${designId}/brand-kit`) });
}

/** Space colours first, then the product palette, without duplicates; anything not #RRGGBB is dropped. */
export function kitSwatches(kit: BrandKit | undefined): Swatch[] {
  const seen = new Set<string>();
  return [...(kit?.colours ?? []), ...brandSwatches()].filter((swatch) => {
    const hex = swatch.hex.toUpperCase();
    if (!HEX.test(hex) || seen.has(hex)) return false;
    seen.add(hex);
    return true;
  }).map((swatch) => ({ label: swatch.label, hex: swatch.hex.toUpperCase() }));
}

export function BrandKitProvider({ designId, children }: { designId: number; children: ReactNode }) {
  const kit = useBrandKit(designId);
  return <BrandContext.Provider value={kitSwatches(kit.data)}>{children}</BrandContext.Provider>;
}

/** The swatch row a colour field shows when a brand kit is in scope (nothing outside the studio). */
export function BrandSwatchRow({ label, value, onPick, disabled }: {
  label: string; value: string | null | undefined; onPick: (hex: string) => void; disabled?: boolean;
}) {
  const swatches = useContext(BrandContext);
  if (!swatches?.length) return null;
  return <div role="group" aria-label={t`${label}: brand colours`} className="flex flex-wrap gap-1">
    {swatches.map((swatch) => <button key={swatch.hex} type="button" disabled={disabled} title={`${swatch.label} ${swatch.hex}`}
      aria-label={`${swatch.label} ${swatch.hex}`} aria-pressed={value?.toUpperCase() === swatch.hex}
      onClick={() => onPick(swatch.hex)}
      className={`h-7 w-7 rounded-control border focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-focus disabled:opacity-40 ${value?.toUpperCase() === swatch.hex ? "border-ink ring-2 ring-accent-ink" : "border-line"}`}
      style={{ background: rgbCss(swatch.hex) }} />)}
  </div>;
}
