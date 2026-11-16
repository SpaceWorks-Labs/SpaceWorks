// Badge geometry: the TypeScript twin of backend apps/card_designs/badge_geometry.py (itself a port of
// SpaceWorks-Events lib/idCardPrint/geometry.ts + defaults.ts). Operations run in the same order as the
// Python so both produce the same numbers; badgeTwin.test.ts checks it against the server fixtures.
// Millimetres unless a name says Pt.

export const ELEMENTS = ["header", "name", "email", "details", "qr", "footer", "logo", "eventLogo", "symbol", "photo",
  "sponsors", "idNumber", "validUntil"] as const;
export type BadgeElement = (typeof ELEMENTS)[number];
export const TEMPLATES = ["classic", "bold", "minimal"] as const;
export type BadgeTemplate = (typeof TEMPLATES)[number];
export type Position = { xMm: number; yMm: number };
export type Positions = Record<BadgeElement, Position>;
export type Sizes = Record<BadgeElement, number>;
export type Flags = { showLogo: boolean; showEventLogo: boolean; showSymbol: boolean; showPhoto: boolean;
  showSponsors: boolean; showIdNumber?: boolean; showValidUntil?: boolean };

const SQUARE = new Set<BadgeElement>(["qr", "logo", "eventLogo", "symbol", "photo"]);
const GRAPHIC = new Set<BadgeElement>([...SQUARE, "sponsors"]);
export const PT_TO_MM = 0.3528;
export const LINE_HEIGHT = { label: 1.2, heading: 1.1, name: 1.1, body: 1.25 } as const;
export const TILE_PADDING_MM = 1;
export const DETAILS_ROW_GAP_MM = 1.5;
export const DETAILS_COLUMN_GAP_MM = 4;
const FLAG_ELEMENT: [keyof Flags, BadgeElement][] = [["showEventLogo", "eventLogo"], ["showSymbol", "symbol"],
  ["showPhoto", "photo"], ["showSponsors", "sponsors"], ["showIdNumber", "idNumber"], ["showValidUntil", "validUntil"]];
export const DEFAULT_FLAGS: Flags = { showLogo: true, showEventLogo: false, showSymbol: true, showPhoto: false, showSponsors: false };

/** Math.round, which is what the Python port calls half_up. */
export const halfUp = (value: number) => Math.floor(value + 0.5);
export const r1 = (value: number) => halfUp(value * 10) / 10;
export const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));
export const isText = (element: BadgeElement) => !GRAPHIC.has(element);
export const isSquare = (element: BadgeElement) => SQUARE.has(element);

export function minimumElementSize(element: BadgeElement) {
  if (element === "symbol") return 7;
  if (element === "photo") return 8;
  return SQUARE.has(element) ? 10 : 20;
}

export const badgeLabelPt = (headerPt: number) => Math.min(9, Math.max(5.5, halfUp(headerPt * 0.5 * 2) / 2));
/** Layout scale relative to A6 (1 on A6): small stock gets proportionally smaller type and margins. */
export const paperScale = (width: number, height: number) => Math.min(1.6, Math.max(0.45, Math.min(width, height) / 105));
const marginMm = (k: number) => Math.max(3, r1(10 * k));
const bandInsetMm = (k: number) => Math.max(4, r1(5 * k));

export function fitTextSizePt(text: string, width: number, sizePt: number, bold: boolean, minRatio = 0.6) {
  const chars = Math.max(1, text.trim().length);
  const fitting = width / (chars * (bold ? 0.6 : 0.54) * 0.3528);
  return r1(Math.max(sizePt * minRatio, Math.min(sizePt, fitting)));
}

export type Decor = {
  frame: { inset: number; rule: number; radius: number } | null;
  headerRule: { gap: number; rule: number } | null;
  band: { padX: number; padY: number; radius: number } | null;
  labelGap: number; nameTrackingEm: number; nameUppercase: boolean;
};

export function templateDecor(template: BadgeTemplate, width: number, height: number): Decor {
  const k = paperScale(width, height);
  const labelGap = Math.max(1, r1(2 * k));
  if (template === "bold") {
    return { frame: null, headerRule: null, labelGap, nameTrackingEm: 0, nameUppercase: true,
      band: { padX: Math.max(2, r1(marginMm(k) - bandInsetMm(k))), padY: Math.max(2, r1(4.5 * k)), radius: Math.max(1, r1(2 * k)) } };
  }
  if (template === "minimal") return { frame: null, headerRule: null, band: null, labelGap, nameTrackingEm: -0.02, nameUppercase: false };
  return { frame: { inset: Math.max(2.5, r1(5 * k)), rule: 0.3, radius: Math.max(1, r1(2.5 * k)) },
    headerRule: { gap: Math.max(1.5, r1(3 * k)), rule: 0.25 }, band: null, labelGap, nameTrackingEm: -0.02, nameUppercase: false };
}

function estimateHeaderHeight(template: BadgeTemplate, headerPt: number, width: number, height: number) {
  const decor = templateDecor(template, width, height);
  let total = badgeLabelPt(headerPt) * PT_TO_MM * LINE_HEIGHT.label + decor.labelGap;
  total += headerPt * PT_TO_MM * LINE_HEIGHT.heading;
  if (decor.headerRule) total += decor.headerRule.gap + decor.headerRule.rule;
  if (decor.band) total += decor.band.padY * 2;
  return r1(total);
}

export const nameBlockHeight = (namePt: number) => r1(namePt * PT_TO_MM * LINE_HEIGHT.name * 1.2);
export const sponsorStripHeight = (width: number, height: number) => clamp(r1(10 * paperScale(width, height)), 6, 14);
const symbolClearSpace = (size: number) => Math.ceil(size * 2.5) / 10;

/** The height the designer keeps clear when it clamps an item to the card (0 for text, which flows). */
export function elementBoxHeight(element: BadgeElement, sizes: Sizes, width: number, height: number) {
  if (SQUARE.has(element)) return sizes[element];
  return element === "sponsors" ? sponsorStripHeight(width, height) : 0;
}

/** The name is always the largest thing on the card; the heading stays small. */
export function defaultTextSizes(template: BadgeTemplate = "classic", width = 105, height = 148): Sizes {
  const base = { bold: [14, 28, 10, 8.5, 7.5, 11, 8.5], minimal: [10, 30, 9.5, 8.5, 7.5, 10, 8.5] }[template as string]
    ?? [13, 30, 10, 8.5, 7.5, 11, 8.5];
  const lows = [6, 9, 6, 6, 6, 6, 6];
  const k = paperScale(width, height);
  const sizes = Object.fromEntries(ELEMENTS.map((element) => [element, 0])) as Sizes;
  (["header", "name", "email", "details", "footer", "idNumber", "validUntil"] as const).forEach((key, index) => {
    sizes[key] = Math.max(lows[index], halfUp(base[index] * k * 2) / 2);
  });
  return sizes;
}

export function defaultBold(): Record<BadgeElement, boolean> {
  const bold = Object.fromEntries(ELEMENTS.map((element) => [element, false])) as Record<BadgeElement, boolean>;
  return { ...bold, header: true, name: true, idNumber: true };
}

function geometry(template: BadgeTemplate, width: number, height: number, flags: Partial<Flags>): [Positions, Sizes] {
  const k = paperScale(width, height);
  const m = marginMm(k);
  const decor = templateDecor(template, width, height);
  const text = defaultTextSizes(template, width, height);
  const line = (pt: number) => pt * PT_TO_MM * LINE_HEIGHT.body;
  const wide = (mm: number) => Math.max(20, r1(mm));
  const qrSize = Math.min(40, Math.max(16, r1((template === "minimal" ? 21 : 24) * k)));
  const logoSize = Math.min(20, Math.max(10, r1((template === "minimal" ? 10 : 12) * k)));
  const symbolSize = clamp(r1(9 * k), 7, 14);
  const photoSize = clamp(r1(24 * k), 12, 34);
  const qr: [number, number] = [r1(width - m - qrSize - 1), r1(height - m - qrSize - 1)];
  const qrLeft = qr[0] + 1;
  const inset = bandInsetMm(k);
  const header: [number, number] = decor.band ? [inset, inset] : [m, m];
  const textX = decor.band ? r1(inset + decor.band.padX) : m;
  const leftOfQr = qrLeft - textX - 4 * k;
  let logo: [number, number] = [r1(width - m - logoSize), m];
  let footerWidth = leftOfQr;
  let sponsorsWidth = leftOfQr;
  if (template === "bold") {
    const beside = qrLeft - 4 * k - logoSize;
    if (beside - textX - 3 * k >= 30) {
      logo = [r1(beside), r1(height - m - logoSize)];
      footerWidth = beside - textX - 3 * k;
      if (flags.showLogo) sponsorsWidth = footerWidth;
    } else {
      logo = [r1(width - m - logoSize), r1(qr[1] + 1 - 3 * k - logoSize)];
    }
  }
  const logoOnTop = template !== "bold" && flags.showLogo;
  const eventLogo: [number, number] = template === "bold" ? [r1(width - inset - logoSize), inset]
    : [r1(logoOnTop ? logo[0] - 3 * k - logoSize : width - m - logoSize), m];
  let headerRight: number;
  if (flags.showEventLogo) headerRight = eventLogo[0] - (template === "bold" ? 2 : 4) * k;
  else headerRight = template === "bold" ? width - inset : logo[0] - 4 * k;
  const headerWidth = decor.band ? wide(headerRight - inset) : wide(headerRight - textX);
  const footerLine = line(text.footer);
  const symbolGap = Math.max(symbolClearSpace(symbolSize), r1(2 * k));
  const besideFooter = footerWidth - symbolSize - symbolGap >= 20;
  const plainFooter: [number, number] = [textX, r1(height - m - footerLine)];
  const symbol: [number, number] = besideFooter ? [textX, r1(height - m - symbolSize)]
    : [textX, r1(plainFooter[1] - symbolGap - symbolSize)];
  const footer: [number, number] = flags.showSymbol && besideFooter
    ? [r1(textX + symbolSize + symbolGap), r1(height - m - symbolSize / 2 - footerLine / 2)] : plainFooter;
  const footerRowTop = flags.showSymbol ? symbol[1] : footer[1];
  const footerBox = flags.showSymbol && besideFooter ? footerWidth - symbolSize - symbolGap : footerWidth;
  const headerBottom = header[1] + estimateHeaderHeight(template, text.header, width, height);
  const nameRatio = template === "bold" ? 0.26 : template === "minimal" ? 0.36 : 0.3;
  const landscape = width > height * 1.15;
  let nameY = r1(Math.max(headerBottom + (template === "minimal" ? 8 : 6) * k, height * nameRatio));
  let contentX = textX;
  let photo: [number, number] = [textX, r1(headerBottom + 4 * k)];
  if (flags.showPhoto) {
    if (landscape) {
      photo = [textX, nameY];
      contentX = r1(textX + photoSize + 3 * k);
    } else {
      nameY = r1(photo[1] + photoSize + 3 * k);
    }
  } else if (landscape) {
    photo = [textX, nameY];
  }
  const emailY = r1(nameY + nameBlockHeight(text.name) + 1.5 * k);
  const idY = r1(emailY + line(text.email) + 2 * k);
  const validY = r1(idY + (flags.showIdNumber ? line(text.idNumber) + 1 * k : 0));
  let memberBottom: number | null = null;
  if (flags.showValidUntil) memberBottom = validY + line(text.validUntil);
  else if (flags.showIdNumber) memberBottom = idY + line(text.idNumber);
  const detailsY = r1(memberBottom === null ? emailY + line(text.email) + 4 * k : memberBottom + 3 * k);
  const full = width - contentX - m;
  const nameWidth = wide(landscape ? Math.min(full, leftOfQr - (contentX - textX)) : full);
  const sponsorsH = sponsorStripHeight(width, height);
  const sponsors: [number, number] = [textX, r1(footerRowTop - Math.max(2 * k, symbolGap) - sponsorsH)];
  const at: Record<BadgeElement, [number, number]> = { header, name: [contentX, nameY], email: [contentX, emailY],
    details: [contentX, detailsY], qr, footer, logo, eventLogo, symbol, photo, sponsors, idNumber: [contentX, idY],
    validUntil: [contentX, validY] };
  const sizes: Sizes = { header: headerWidth, name: nameWidth, email: nameWidth, details: wide(leftOfQr - (contentX - textX)),
    qr: qrSize, footer: wide(footerBox), logo: logoSize, eventLogo: logoSize, symbol: symbolSize, photo: photoSize,
    sponsors: wide(sponsorsWidth), idNumber: nameWidth, validUntil: nameWidth };
  const positions = Object.fromEntries(ELEMENTS.map((element) => [element, { xMm: at[element][0], yMm: at[element][1] }])) as Positions;
  return [positions, sizes];
}

/** Where an optional item goes when it is turned on, without reflowing the rest. */
export function geometryWithOptionalDefaults(template: BadgeTemplate, width: number, height: number,
  flags: Partial<Flags>): [Positions, Sizes] {
  const merged: Partial<Flags> = { ...DEFAULT_FLAGS };
  for (const [key, value] of Object.entries(flags)) merged[key as keyof Flags] = Boolean(value);
  const [positions, sizes] = geometry(template, width, height, merged);
  for (const [flag, element] of FLAG_ELEMENT) {
    if (merged[flag]) continue;
    const [onPositions, onSizes] = geometry(template, width, height, { ...merged, [flag]: true });
    positions[element] = onPositions[element];
    sizes[element] = onSizes[element];
  }
  return [positions, sizes];
}

export function layoutForPaper(template: BadgeTemplate, width: number, height: number, flags: Partial<Flags> = DEFAULT_FLAGS) {
  const [elementPositions, elementSizes] = geometryWithOptionalDefaults(template, width, height, flags);
  return { elementPositions, elementSizes, elementTextSizes: defaultTextSizes(template, width, height), elementBold: defaultBold() };
}

/** The point size the name prints at after auto-fit (a long name shrinks, never below 30 %). */
export function nameSizePt(settings: { elementTextSizes: Sizes; elementSizes: Sizes; elementBold: Record<BadgeElement, boolean>;
  nameAutoFit: boolean; template: BadgeTemplate; widthMm: number; heightMm: number }, name: string) {
  const size = settings.elementTextSizes.name;
  if (!settings.nameAutoFit) return size;
  const upper = templateDecor(settings.template, settings.widthMm, settings.heightMm).nameUppercase;
  const width = settings.elementSizes.name / (upper ? 1.15 : 1);
  const bold = settings.elementBold.name || upper;
  const fitted = fitTextSizePt(name, width, size, bold);
  const emMm = (bold ? 0.6 : 0.54) * PT_TO_MM;
  const chars = Math.max(1, name.trim().length);
  const area = 0.85 * Math.sqrt((1.2 * size * width) / (chars * emMm));
  return r1(Math.min(fitted, Math.max(size * 0.3, area)));
}
