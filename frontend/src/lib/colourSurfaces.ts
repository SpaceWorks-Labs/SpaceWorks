import { t } from "@lingui/core/macro";
import type { CSSProperties } from "react";
import { BODY_TEXT, BRAND_SURFACES, FIXED_INKS, FIXED_SOFTS, PRODUCT_FILL, type RGB } from "./brandColours";

export type SurfaceId = "staff" | "member" | "public" | "printed" | "screens";
export type ColourUse = "primary" | "accent" | "derived" | "none";
export type Surface = { id: SurfaceId; title: string; audience: string; roles: string[]; uses: ColourUse; note: string; examples: string };

/** Who sees each surface, and which of the two space colours (plus what is derived from them) it takes. */
export function colourSurfaces(): Surface[] {
  return [
    { id: "staff", title: t`Staff console`, audience: t`Staff`, uses: "none",
      roles: [t`Space Manager`, t`Inventory Manager`, t`Machine Manager`, t`Custom roles`],
      examples: t`Sidebar, buttons, badges, tables`,
      note: t`Always the Space Works palette, so every staff role reads the same screen. Space colours never change it.` },
    { id: "member", title: t`Member app`, audience: t`Members`, uses: "derived",
      roles: [t`Member`], examples: t`Account cards, activity, brand buttons and links`,
      note: t`Primary fill drives buttons; the link colour drives links and outlines. Soft, hover and active shades are derived.` },
    { id: "public", title: t`Public pages`, audience: t`Visitors`, uses: "derived",
      roles: [t`Anyone, no sign-in`], examples: t`Space page, public inventory, bookings, events website, donations`,
      note: t`Same derived brand colours as the member app. A page can still choose its own accent in its page design.` },
    { id: "printed", title: t`Printed and shared`, audience: t`Members and visitors`, uses: "accent",
      roles: [t`Anyone who receives a document`], examples: t`Receipts, invoices, credit notes`,
      note: t`Receipts and invoices use the link colour as their header accent, or Workshop Orange when it is blank. ID cards, certificates and wallet passes keep their own colours from the card and certificate designers.` },
    { id: "screens", title: t`Screens`, audience: t`People in the space`, uses: "accent",
      roles: [t`Anyone looking at the display`], examples: t`Live stats TV, events calendar on the space display`,
      note: t`Numbers and labels keep the standard ink and grey on panel tiles; only links use your link colour. The desk kiosk keeps the standard palette.` },
  ];
}

export function useLabels(): Record<ColourUse, string> {
  return { primary: t`Primary fill`, accent: t`Link colour`, derived: t`Primary fill and link colour`, none: t`No space colours` };
}

// Mirrors the literal token blocks in index.css (guarded by colourSurfaces.test.ts); previews scope them to one box.
export const PREVIEW_LINE: Record<"light" | "dark", [RGB, RGB]> = { light: [[213, 208, 198], [130, 138, 131]], dark: [[44, 44, 44], [120, 120, 120]] };
const v = (c: RGB) => c.join(" ");

export function previewBaseVars(mode: "light" | "dark"): CSSProperties {
  const [bg, surface, panel, hover] = BRAND_SURFACES[mode];
  const fill = PRODUCT_FILL[mode];
  return {
    "--color-bg": v(bg), "--color-surface": v(surface), "--color-panel": v(panel), "--color-hover": v(hover),
    "--color-line": v(PREVIEW_LINE[mode][0]), "--color-outline": v(PREVIEW_LINE[mode][1]),
    "--color-ink": v(BODY_TEXT[mode][0]), "--color-muted": v(BODY_TEXT[mode][1]),
    "--color-focus": mode === "light" ? v(fill) : "223 255 143",
    "--color-accent": v(fill), "--color-accent-hover": "2 103 93", "--color-accent-active": "4 97 88",
    "--color-on-accent": "255 244 232", "--color-accent-soft": v(FIXED_SOFTS[mode][0]), "--color-accent-ink": v(FIXED_INKS[mode][0]),
  } as CSSProperties;
}
