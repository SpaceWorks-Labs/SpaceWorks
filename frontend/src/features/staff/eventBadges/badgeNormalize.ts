// The badge_v1 settings document: TypeScript twin of backend apps/card_designs/badge_format.py. The keys are
// the SpaceWorks-Events IdCardPrintSettings verbatim (camelCase), so an Events design file opens unchanged.
// Anything unexpected becomes a default, and positions and sizes are clamped to the card. The server
// normalises again on every save; this copy lets the designer draw what the server will store.
import {
  clamp, defaultBold, defaultTextSizes, DEFAULT_FLAGS, elementBoxHeight, ELEMENTS, geometryWithOptionalDefaults, halfUp,
  isText, layoutForPaper, minimumElementSize, r1, TEMPLATES,
  type BadgeElement, type BadgeTemplate, type Flags, type Positions, type Sizes,
} from "./badgeGeometry";

export const PRINT_FIELD_MAX = 8;
export const SPONSOR_LIMIT_MAX = 6;
export const TEAM_FIELD_KEY = "attendee:team";
export const CREW_KIND_FIELD_KEY = "attendee:crew_kind";
export const GRID_SIZES = [1, 2, 5, 10] as const;
export const BACKGROUND_KEYS = ["white", "cream", "ink", "teal", "citron", "sky", "event"] as const;
export const ACCENT_KEYS = ["event", "teal", "ink", "orange", "citron", "sky", "yellow"] as const;
export const TEXT_KEYS = ["auto", "ink", "teal", "cream", "white"] as const;
export const TEXT_LIMITS = { heading: 120, badgeLabel: 40, footerText: 240 } as const;
const MIN_DIMENSION_MM = 40;
const MAX_DIMENSION_MM = 300;

export type Watermark = { kind: "none" | "text" | "image"; text: string; opacityPct: number; colour: "accent" | "text"; angleDeg: number };
export type BadgeSettings = {
  widthMm: number; heightMm: number; heading: string; badgeLabel: string; showEmail: boolean; template: BadgeTemplate;
  footerText: string; printFieldKeys: string[]; printFieldLabels: Record<string, string>; elementPositions: Positions;
  elementSizes: Sizes; elementBold: Record<BadgeElement, boolean>; elementTextSizes: Sizes; gridSizeMm: (typeof GRID_SIZES)[number];
  showGrid: boolean; nameAutoFit: boolean; showBadgeLabel: boolean; showFooter: boolean; colorMode: "colour" | "mono";
  backgroundColor: (typeof BACKGROUND_KEYS)[number]; accentColor: (typeof ACCENT_KEYS)[number]; textColor: (typeof TEXT_KEYS)[number];
  showLogo: boolean; showEventLogo: boolean; showSymbol: boolean; showPhoto: boolean; showSponsors: boolean;
  showIdNumber: boolean; showValidUntil: boolean; photoShape: "circle" | "rounded"; sponsorLimit: number; showName: boolean;
  showQr: boolean; idNumberLabel: string; validUntilLabel: string; watermark: Watermark;
};

const DEFAULT_WATERMARK: Watermark = { kind: "none", text: "", opacityPct: 10, colour: "accent", angleDeg: -30 };
type Loose = Record<string, unknown>;

export function defaultSettings(eventTitle = "", organisationName = ""): BadgeSettings {
  const layout = layoutForPaper("classic", 105, 148);
  return {
    widthMm: 105, heightMm: 148,
    // i18n-ignore: stored-document default; must equal backend badge_format.default_settings (golden fixtures)
    heading: eventTitle.trim().slice(0, 120) || "Event attendee", badgeLabel: "ATTENDEE", showEmail: true, template: "classic",
    // i18n-ignore: stored-document default; must equal backend badge_format.default_settings (golden fixtures)
    footerText: organisationName.trim().slice(0, 80) || "Event check-in",
    printFieldKeys: [], printFieldLabels: {}, ...layout, gridSizeMm: 5, showGrid: true, nameAutoFit: true,
    showBadgeLabel: true, showFooter: true, colorMode: "colour", backgroundColor: "white", accentColor: "event",
    textColor: "auto", ...DEFAULT_FLAGS, showIdNumber: false, showValidUntil: false, photoShape: "circle", sponsorLimit: 4,
    showName: true, showQr: true, idNumberLabel: "ID", validUntilLabel: "Valid until", watermark: { ...DEFAULT_WATERMARK },
  };
}

/** Python's float(): numbers and numeric strings; booleans, blanks and non-finite values are not numbers. */
function num(value: unknown): number | null {
  if (typeof value === "boolean") return null;
  const number = typeof value === "number" ? value : typeof value === "string" && value.trim() ? Number(value.trim()) : NaN;
  return Number.isFinite(number) ? number : null;
}
const record = (value: unknown): Loose => (value && typeof value === "object" && !Array.isArray(value) ? value as Loose : {});
const bool = (value: unknown, fallback: boolean) => (typeof value === "boolean" ? value : fallback);
const oneOf = <T extends string>(value: unknown, allowed: readonly T[], fallback: T): T =>
  (typeof value === "string" && (allowed as readonly string[]).includes(value) ? value as T : fallback);
const text = (value: unknown, fallback: string, limit: number) =>
  (typeof value === "string" ? [...value.trim()].slice(0, limit).join("") || fallback : fallback);
const label = (value: unknown, fallback: string) => (typeof value === "string" ? value.trim().slice(0, 30) : fallback);

const TEAM_TAG = /\{\{\s*team\s*\}\}/;
/** Heading, label and footer carry the {{team}} tag and nothing else in braces. */
export function mergeOnly(value: string) {
  const cleaned = value.replace(/\{\{[^{}]*\}\}/g, (match) => (new RegExp(`^${TEAM_TAG.source}$`).test(match) ? match : ""));
  return cleaned.split(new RegExp(TEAM_TAG.source, "g")).map((part) => part.replace(/[{}]/g, "")).join("{{team}}");
}

function positions(value: unknown, fallback: Positions, width: number, height: number): Positions {
  const result = {} as Positions;
  for (const element of ELEMENTS) {
    const item = record(record(value)[element]);
    const x = num(item.xMm), y = num(item.yMm);
    result[element] = { xMm: x === null ? fallback[element].xMm : Math.min(width - 4, Math.max(0, r1(x))),
      yMm: y === null ? fallback[element].yMm : Math.min(height - 4, Math.max(0, r1(y))) };
  }
  return result;
}

function sizes(value: unknown, fallback: Sizes, width: number): Sizes {
  const result = {} as Sizes;
  for (const element of ELEMENTS) {
    const size = num(record(value)[element]);
    const low = minimumElementSize(element);
    result[element] = size === null ? fallback[element] : Math.min(Math.max(low, width - 4), Math.max(low, r1(size)));
  }
  return result;
}

function fitPositions(at: Positions, size: Sizes, width: number, height: number): Positions {
  const result = {} as Positions;
  for (const element of ELEMENTS) {
    const box = elementBoxHeight(element, size, width, height);
    result[element] = { xMm: Math.min(Math.max(0, width - size[element] - 4), at[element].xMm),
      yMm: box > 0 ? Math.min(Math.max(0, height - box - 4), at[element].yMm) : at[element].yMm };
  }
  return result;
}

function textSizes(value: unknown, template: BadgeTemplate, width: number, height: number): Sizes {
  const fallback = defaultTextSizes(template, width, height);
  const result = {} as Sizes;
  for (const element of ELEMENTS) {
    const size = isText(element) ? num(record(value)[element]) : null;
    result[element] = !isText(element) ? 0 : size === null ? fallback[element] : Math.min(48, Math.max(6, r1(size)));
  }
  return result;
}

function fieldKeys(value: unknown) {
  if (!Array.isArray(value)) return [];
  const keys: string[] = [];
  for (const raw of value) {
    const item = typeof raw === "string" ? raw.trim() : "";
    if (item && item.length <= 160 && !item.startsWith("system:") && !keys.includes(item)) keys.push(item);
  }
  return keys.slice(0, PRINT_FIELD_MAX);
}

function fieldLabels(value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(Object.entries(value as Loose).slice(0, 16)
    .filter(([key, item]) => key.length <= 160 && typeof item === "string")
    .map(([key, item]) => [key, (item as string).trim().slice(0, 60)]));
}

function watermark(value: unknown): Watermark {
  if (!value || typeof value !== "object" || Array.isArray(value)) return { ...DEFAULT_WATERMARK };
  const given = value as Loose;
  const opacity = num(given.opacityPct), angle = num(given.angleDeg);
  return { kind: oneOf(given.kind, ["none", "text", "image"] as const, "none"),
    text: typeof given.text === "string" ? given.text.trim().slice(0, 32) : "",
    opacityPct: opacity === null ? 10 : clamp(halfUp(opacity), 4, 30),
    colour: oneOf(given.colour, ["accent", "text"] as const, "accent"),
    angleDeg: angle === null ? -30 : clamp(halfUp(angle), -90, 90) };
}

/** Any value -> a complete, safe settings object (the server's `normalize`, non-strict). */
export function normalizeSettings(input: unknown, eventTitle = "", organisationName = ""): BadgeSettings {
  const fallback = defaultSettings(eventTitle, organisationName);
  if (!input || typeof input !== "object" || Array.isArray(input)) return fallback;
  const value = input as Loose;
  const legacy = Object.keys(value).length > 0 && !("colorMode" in value);
  const width = clamp(r1(num(value.widthMm) ?? fallback.widthMm), MIN_DIMENSION_MM, MAX_DIMENSION_MM);
  const height = clamp(r1(num(value.heightMm) ?? fallback.heightMm), MIN_DIMENSION_MM, MAX_DIMENSION_MM);
  const template = oneOf(value.template, TEMPLATES, "classic");
  const flags = { showLogo: bool(value.showLogo, true) } as Flags & { showIdNumber: boolean; showValidUntil: boolean };
  for (const key of ["showEventLogo", "showSymbol", "showPhoto", "showSponsors"] as const) {
    flags[key] = bool(value[key], legacy ? false : fallback[key]);
  }
  flags.showIdNumber = bool(value.showIdNumber, false);
  flags.showValidUntil = bool(value.showValidUntil, false);
  const [basePositions, baseSizes] = geometryWithOptionalDefaults(template, width, height, flags);
  const elementSizes = sizes(value.elementSizes, baseSizes, width);
  const at = positions(value.elementPositions, basePositions, width, height);
  const sponsorLimit = num(value.sponsorLimit);
  const bold = defaultBold();
  const givenBold = record(value.elementBold);
  const gridSize = num(value.gridSizeMm);
  return {
    widthMm: width, heightMm: height,
    heading: mergeOnly(text(value.heading, fallback.heading, 120)),
    badgeLabel: mergeOnly(text(value.badgeLabel, fallback.badgeLabel, 40)),
    showEmail: bool(value.showEmail, true), template,
    footerText: mergeOnly(text(value.footerText, fallback.footerText, TEXT_LIMITS.footerText)),
    printFieldKeys: fieldKeys(value.printFieldKeys), printFieldLabels: fieldLabels(value.printFieldLabels),
    elementPositions: fitPositions(at, elementSizes, width, height), elementSizes,
    elementBold: Object.fromEntries(ELEMENTS.map((key) => [key,
      isText(key) && typeof givenBold[key] === "boolean" ? givenBold[key] as boolean : bold[key]])) as Record<BadgeElement, boolean>,
    elementTextSizes: textSizes(value.elementTextSizes, template, width, height),
    gridSizeMm: GRID_SIZES.find((size) => size === gridSize) ?? 5,
    showGrid: bool(value.showGrid, true), nameAutoFit: bool(value.nameAutoFit, true),
    showBadgeLabel: bool(value.showBadgeLabel, true), showFooter: bool(value.showFooter, true),
    colorMode: legacy ? "mono" : oneOf(value.colorMode, ["colour", "mono"] as const, "colour"),
    backgroundColor: oneOf(value.backgroundColor, BACKGROUND_KEYS, "white"),
    accentColor: oneOf(value.accentColor, ACCENT_KEYS, "event"),
    textColor: oneOf(value.textColor, TEXT_KEYS, "auto"), ...flags,
    photoShape: oneOf(value.photoShape, ["circle", "rounded"] as const, "circle"),
    sponsorLimit: sponsorLimit === null ? 4 : clamp(halfUp(sponsorLimit), 1, SPONSOR_LIMIT_MAX),
    showName: bool(value.showName, true), showQr: bool(value.showQr, true),
    idNumberLabel: label(value.idNumberLabel, "ID"), validUntilLabel: label(value.validUntilLabel, "Valid until"),
    watermark: watermark(value.watermark),
  };
}

export function layoutFlags(settings: BadgeSettings): Partial<Flags> {
  return { showLogo: settings.showLogo, showEventLogo: settings.showEventLogo, showSymbol: settings.showSymbol,
    showPhoto: settings.showPhoto, showSponsors: settings.showSponsors,
    ...(settings.showIdNumber ? { showIdNumber: true } : {}), ...(settings.showValidUntil ? { showValidUntil: true } : {}) };
}

const sameLayout = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** True while positions and sizes are untouched, so a stock or toggle change may reflow them. */
export function isDefaultLayout(settings: BadgeSettings, flags = layoutFlags(settings)) {
  const fresh = layoutForPaper(settings.template, settings.widthMm, settings.heightMm, flags);
  return ELEMENTS.every((element) => sameLayout(fresh.elementPositions[element], settings.elementPositions[element])
    && fresh.elementSizes[element] === settings.elementSizes[element]);
}
