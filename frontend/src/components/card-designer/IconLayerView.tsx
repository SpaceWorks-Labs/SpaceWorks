// Icon layers (decision 344(b)): one vendored vector icon, contained and centred in its box, one colour.
// The TS twin of backend apps/card_designs/rendering_icons.py: same paths (studioIcons.json, a copy of
// studio_icons.json), each filled on its own with the even-odd rule, mono maps the colour to black or white.
import { t } from "@lingui/core/macro";

import type { Layer } from "./cardTypes";
import { luminance, rgb } from "./contrast";
import icons from "./studioIcons.json";
import { rgbCss } from "./studioMath";

type IconEntry = { label: string; paths: string[] };
const CATALOGUE = icons.icons as Record<string, IconEntry>;

export const ICON_KEYS = Object.keys(CATALOGUE);
export const iconPaths = (key: string | undefined) => (key ? CATALOGUE[key]?.paths ?? [] : []);

/** Translated icon names for the picker (the JSON labels are the English source). */
export function iconLabel(key: string) {
  const labels: Record<string, string> = {
    star: t`Star`, sparkle: t`Sparkle`, heart: t`Heart`, check: t`Tick`, check_circle: t`Tick in a circle`, close: t`Cross`,
    plus: t`Plus`, pin: t`Location pin`, user: t`Person`, home: t`Home`, bolt: t`Lightning`, shield: t`Shield`,
    award: t`Award`, clock: t`Clock`, calendar: t`Calendar`, mail: t`Envelope`, phone: t`Phone`, id_card: t`ID card`,
    key: t`Key`, gear: t`Gear`, info: t`Information`, alert: t`Warning`, arrow_right: t`Arrow`, chevron_right: t`Chevron`,
    printer: t`Printer`, wrench: t`Wrench`, globe: t`Globe`, wifi: t`Wireless`, camera: t`Camera`, cube: t`Box`,
  };
  return labels[key] ?? CATALOGUE[key]?.label ?? key;
}

/** The icon glyph alone (used by the layer view and the picker). */
export function IconGlyph({ icon, colour, flip }: { icon: string | undefined; colour: string; flip?: boolean }) {
  return <svg viewBox="0 0 24 24" className="block h-full w-full" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
    <g transform={flip ? "translate(24 0) scale(-1 1)" : undefined}>
      {iconPaths(icon).map((d, index) => <path key={index} d={d} fill={colour} fillRule="evenodd" />)}
    </g>
  </svg>;
}

export function IconLayerView({ layer, mono }: { layer: Layer; mono: boolean }) {
  const colour = layer.colour ?? "#142C2A";
  const paint = mono ? (luminance(rgb(colour)) < 0.4 ? "#000000" : "#FFFFFF") : rgbCss(colour);
  return <IconGlyph icon={layer.icon} colour={paint} flip={layer.flip_x} />;
}
