// Compile badge settings to card layers: the TypeScript twin of backend apps/card_designs/badge_compile.py.
// The server recompiles on every save (client layers are ignored); the designer compiles the same way so its
// preview is what prints. Each layer also records the badge item it belongs to, for selection and dragging.
// Layer ids here are the readable keys; the server's are uuid5 values of the same keys.
import {
  clamp, DETAILS_COLUMN_GAP_MM, DETAILS_ROW_GAP_MM, LINE_HEIGHT, nameBlockHeight, PT_TO_MM, r1, sponsorStripHeight,
  templateDecor, TILE_PADDING_MM, badgeLabelPt, type BadgeElement, type Decor,
} from "./badgeGeometry";
import { CREW_KIND_FIELD_KEY, TEAM_FIELD_KEY, type BadgeSettings } from "./badgeNormalize";
import { resolvePalette, type BadgePalette } from "./badgePalette";

const STOCKS: Record<string, [number, number]> = {
  "cr80-landscape": [85.6, 53.98], "cr80-portrait": [53.98, 85.6], "cr79-landscape": [83.9, 52.1],
  "cr79-portrait": [52.1, 83.9], "cr100-landscape": [98.5, 67.0], "cr100-portrait": [67.0, 98.5],
  "a6-portrait": [105.0, 148.0], "a6-landscape": [148.0, 105.0], "4x3": [101.6, 76.2], "3x4": [76.2, 101.6],
  "4x6": [101.6, 152.4], "6x4": [152.4, 101.6],
};
const PHOTO_SYMBOL_ASPECT = 136 / 126;
const SPONSOR_GAP_MM = 2;
const ANSWER_KEY = /^[a-z0-9_]{1,40}$/;

export type BadgeLayer = Record<string, unknown> & { id: string; kind: string; name: string; x_mm: number; y_mm: number;
  w_mm: number; h_mm: number; element: BadgeElement | null };
export type CompiledBadge = { stock: string; page_width_mm: number; page_height_mm: number; mono: boolean;
  watermark: { kind: "none" | "text"; text: string; asset_id: null; opacity_pct: number; angle_deg: number; colour: string };
  background: string; layers: BadgeLayer[]; palette: BadgePalette };

export function stockFor(width: number, height: number): [string, number, number] {
  for (const [key, [w, h]] of Object.entries(STOCKS)) {
    if (Math.abs(w - width) < 0.05 && Math.abs(h - height) < 0.05) return [key, w, h];
  }
  return ["custom", r1(width), r1(height)];
}
const qrMinimum = (stock: string) => (["cr80", "cr79", "cr100"].includes(stock.split("-")[0]) ? 18 : 20);

/** A settings field key (`registration:<k>`, `<k>`, `attendee:team`) -> a data-field tag, or null. */
export function fieldTag(key: string) {
  if (key === TEAM_FIELD_KEY) return "team";
  if (key === CREW_KIND_FIELD_KEY) return "crew_kind";
  const answer = key.startsWith("registration:") ? key.slice("registration:".length) : key;
  return ANSWER_KEY.test(answer) ? `field:${answer}` : null;
}

export function defaultLabel(key: string, labels: { team: string; role: string } = { team: "Team", role: "Role" }) {
  if (key === TEAM_FIELD_KEY) return labels.team;
  if (key === CREW_KIND_FIELD_KEY) return labels.role;
  const name = (key.includes(":") ? key.slice(key.indexOf(":") + 1) : key).replace(/_/g, " ").trim();
  return name.slice(0, 1).toUpperCase() + name.slice(1);
}

const braceless = (value: string) => value.replace(/[{}]/g, "");
const line = (pt: number, kind: keyof typeof LINE_HEIGHT = "body") => pt * PT_TO_MM * LINE_HEIGHT[kind];
const round2 = (value: number) => Math.round(value * 100) / 100;

type TextOptions = { pt: number; colour: string; text?: string; field?: string; bold?: boolean; align?: string;
  trackingEm?: number; upper?: boolean; shrink?: boolean };

class Builder {
  layers: BadgeLayer[] = [];
  constructor(readonly width: number, readonly height: number) {}

  add(element: BadgeElement | null, kind: string, key: string, name: string, x: number, y: number, w: number, h: number,
    extra: Record<string, unknown> = {}) {
    w = clamp(w, 0.5, this.width);
    h = clamp(h, 0.3, this.height);
    x = clamp(x, 0, this.width - w);
    y = clamp(y, 0, this.height - h);
    this.layers.push({ id: key, kind, name: name.slice(0, 40), x_mm: round2(x), y_mm: round2(y), w_mm: round2(w),
      h_mm: round2(h), rotation: 0, opacity: 100, locked: false, hidden: false, ...extra, element });
  }

  text(element: BadgeElement, key: string, name: string, x: number, y: number, w: number, h: number, options: TextOptions) {
    const size = clamp(options.pt, 6, 96);
    const row = { font_family: "Outfit", font_weight: options.bold ? 700 : 400, font_size_pt: size,
      align: options.align ?? "left", valign: "top", colour: options.colour, uppercase: options.upper ?? false,
      tracking_pt: clamp(round2((options.trackingEm ?? 0) * size), -2, 10), line_height: LINE_HEIGHT.body,
      shrink_to_fit: options.shrink ?? true };
    if (options.field) this.add(element, "data_field", key, name, x, y, w, h, { field: options.field, ...row });
    else this.add(element, "text", key, name, x, y, w, h, { text: options.text, ...row });
  }
}

function header(build: Builder, settings: BadgeSettings, palette: BadgePalette, decor: Decor) {
  const label = settings.showBadgeLabel ? settings.badgeLabel : "";
  const heading = settings.heading;
  if (!(label.trim() || heading.trim())) return;
  const at = settings.elementPositions.header, size = settings.elementSizes.header, pt = settings.elementTextSizes.header;
  const bold = settings.elementBold.header;
  const band = decor.band;
  const x = at.xMm + (band ? band.padX : 0);
  const width = size - (band ? 2 * band.padX : 0);
  let cursor = at.yMm + (band ? band.padY : 0);
  const colour = band ? palette.on_accent : palette.heading;
  const labelPt = badgeLabelPt(pt);
  const labelH = line(labelPt, "label"), headingH = line(pt, "heading");
  let top = cursor;
  cursor += (label.trim() ? labelH + decor.labelGap : 0) + (heading.trim() ? headingH : 0);
  if (band) {
    build.add("header", "band", "header-band", "Heading band", at.xMm, at.yMm, size, cursor + band.padY - at.yMm,
      { fill: palette.accent, radius_mm: band.radius });
  }
  if (label.trim()) {
    build.text("header", "header-label", "Badge label", x, top, width, labelH,
      { pt: labelPt, colour, text: label, bold, trackingEm: 0.16, shrink: false });
    top += labelH + decor.labelGap;
  }
  if (heading.trim()) {
    build.text("header", "header-heading", "Heading", x, top, width, headingH, { pt, colour, text: heading, bold, trackingEm: -0.01 });
  }
  if (decor.headerRule) {
    build.add("header", "shape", "header-rule", "Heading rule", at.xMm, cursor + decor.headerRule.gap, size,
      Math.max(0.3, decor.headerRule.rule), { shape: "rect", fill: palette.rule, stroke: null, stroke_mm: 0.3, radius_mm: 0 });
  }
}

function details(build: Builder, settings: BadgeSettings, palette: BadgePalette, labels?: Record<string, string>) {
  const at = settings.elementPositions.details, width = settings.elementSizes.details, pt = settings.elementTextSizes.details;
  const bold = settings.elementBold.details;
  let cursor = at.yMm;
  const rowH = line(pt);
  settings.printFieldKeys.forEach((key, index) => {
    const tag = fieldTag(key);
    if (tag === null || cursor === Infinity) return;
    cursor += DETAILS_ROW_GAP_MM;
    if (cursor + rowH > build.height) { cursor = Infinity; return; }
    let label = settings.printFieldLabels[key];
    if (label === undefined) label = labels?.[key] || defaultLabel(key);
    label = braceless(label);
    let valueX = at.xMm, valueW = width, align = "left";
    if (label) {
      const natural = label.length * 0.54 * pt * PT_TO_MM;
      const labelW = Math.min(natural, width * 0.5);
      build.text("details", `field-${index}-label`, `Answer ${index + 1} label`, at.xMm, cursor, labelW + 0.01, rowH,
        { pt, colour: palette.text, text: label, bold });
      valueX = at.xMm + labelW + DETAILS_COLUMN_GAP_MM; valueW = width - labelW - DETAILS_COLUMN_GAP_MM; align = "right";
    }
    build.text("details", `field-${index}-value`, `Answer ${index + 1}`, valueX, cursor, valueW, rowH,
      { pt, colour: palette.text, field: tag, bold, align });
    cursor += rowH;
  });
}

function graphics(build: Builder, settings: BadgeSettings, palette: BadgePalette, stock: string) {
  const at = settings.elementPositions, size = settings.elementSizes, pad = TILE_PADDING_MM;
  if (settings.showLogo) {
    build.add("logo", "logo", "logo", "Organisation logo", at.logo.xMm, at.logo.yMm, size.logo, size.logo, { source: "organisation", tile: true });
  }
  if (settings.showEventLogo) {
    build.add("eventLogo", "logo", "event-logo", "Event logo", at.eventLogo.xMm, at.eventLogo.yMm, size.eventLogo, size.eventLogo,
      { source: "event", tile: true });
  }
  if (settings.showSponsors) {
    const stripH = sponsorStripHeight(build.width, build.height);
    const { xMm: sx, yMm: sy } = at.sponsors, sw = size.sponsors;
    build.add("sponsors", "shape", "sponsor-strip", "Sponsor strip", sx, sy, sw, stripH,
      { shape: "rect", fill: palette.tile, stroke: null, stroke_mm: 0.3, radius_mm: Math.min(2, stripH / 4) });
    const count = settings.sponsorLimit;
    const slot = (sw - 2 * pad - SPONSOR_GAP_MM * (count - 1)) / count;
    for (let index = 0; index < count; index += 1) {
      build.add("sponsors", "logo", `sponsor-${index + 1}`, `Sponsor ${index + 1}`, sx + pad + index * (slot + SPONSOR_GAP_MM),
        sy + pad, slot, stripH - 2 * pad, { source: `sponsor_${index + 1}`, tile: false });
    }
  }
  if (settings.showPhoto) {
    build.add("photo", "photo", "photo", "Photo", at.photo.xMm, at.photo.yMm, size.photo, size.photo,
      { shape: settings.photoShape, filter: "none", duotone_dark: "#142C2A", duotone_light: "#DFFF8F" });
  }
  if (settings.showSymbol) {
    const side = size.symbol, symbolH = side / PHOTO_SYMBOL_ASPECT;
    build.add("symbol", "logo", "symbol", "Space Works symbol", at.symbol.xMm, at.symbol.yMm + (side - symbolH) / 2, side, symbolH,
      { source: "symbol", tile: false });
  }
  if (settings.showQr) {
    const side = Math.min(Math.max(size.qr + 2 * pad, qrMinimum(stock)), build.width, build.height);
    build.add("qr", "checkin_qr", "checkin-qr", "Check-in QR", at.qr.xMm, at.qr.yMm, side, side);
  }
}

export function compileBadge(settings: BadgeSettings, options: { eventAccent?: string | null; fieldLabels?: Record<string, string> } = {}): CompiledBadge {
  const [stock, width, height] = stockFor(settings.widthMm, settings.heightMm);
  const palette = resolvePalette(settings, options.eventAccent);
  const decor = templateDecor(settings.template, width, height);
  const { elementPositions: at, elementSizes: size, elementTextSizes: pt, elementBold: bold } = settings;
  const build = new Builder(width, height);
  if (decor.frame) {
    const frame = decor.frame;
    build.add(null, "shape", "frame", "Frame", frame.inset, frame.inset, width - 2 * frame.inset, height - 2 * frame.inset,
      { shape: "rect", fill: null, stroke: palette.rule, stroke_mm: frame.rule, radius_mm: Math.min(20, frame.radius) });
  }
  header(build, settings, palette, decor);
  if (settings.showName) {
    build.text("name", "name", "Name", at.name.xMm, at.name.yMm, size.name, nameBlockHeight(pt.name), { pt: pt.name,
      colour: palette.text, field: "name", bold: bold.name || decor.nameUppercase, trackingEm: decor.nameTrackingEm,
      upper: decor.nameUppercase, shrink: settings.nameAutoFit });
  }
  for (const [flag, element, tag, labelKey] of [["showIdNumber", "idNumber", "number", "idNumberLabel"],
    ["showValidUntil", "validUntil", "valid_until", "validUntilLabel"]] as const) {
    if (!settings[flag]) continue;
    const label = braceless(settings[labelKey]).trim();
    build.text(element, element, element, at[element].xMm, at[element].yMm, size[element], line(pt[element]), { pt: pt[element],
      colour: palette.text, text: `${label} {{${tag}}}`.trim(), bold: bold[element], trackingEm: element === "idNumber" ? 0.02 : 0 });
  }
  if (settings.showEmail) {
    build.text("email", "email", "Email", at.email.xMm, at.email.yMm, size.email, line(pt.email),
      { pt: pt.email, colour: palette.text, field: "email", bold: bold.email });
  }
  details(build, settings, palette, options.fieldLabels);
  if (settings.showFooter && settings.footerText.trim()) {
    build.text("footer", "footer", "Footer", at.footer.xMm, at.footer.yMm, size.footer, line(pt.footer), { pt: pt.footer,
      colour: palette.text, text: settings.footerText, bold: bold.footer || settings.template === "bold" });
  }
  graphics(build, settings, palette, stock);
  const mark = settings.watermark;
  const markText = braceless(mark.text).trim().toUpperCase();
  const markKind = mark.kind === "text" && markText ? "text" : "none";
  return { stock, page_width_mm: width, page_height_mm: height, mono: settings.colorMode === "mono",
    watermark: { kind: markKind, text: markKind === "text" ? markText : "", asset_id: null, opacity_pct: mark.opacityPct,
      angle_deg: clamp(mark.angleDeg, -60, 60),
      colour: mark.colour === "text" || palette.accent === palette.background ? palette.text : palette.accent },
    background: palette.background, layers: build.layers, palette };
}
