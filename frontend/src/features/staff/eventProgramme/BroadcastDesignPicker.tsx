import type { CSSProperties } from "react";
import { BROADCAST_DESIGNS, type BroadcastDesign } from "./broadcastApi";

// The email designs use fixed Space Works brand colours (docs/brand), not the app theme,
// so each card shows the message as it renders in a light and in a dark mail client.
const INK = "20 44 42", CREAM = "255 244 232", TEAL = "0 110 99", ORANGE = "255 116 71", CITRON = "223 255 143", SKY = "181 205 255";
const LIGHT: Record<BroadcastDesign, string> = { classic: TEAL, bold: ORANGE, minimal: INK, accent_band: TEAL, photo_header: SKY, letter: INK };
const DARK: Record<BroadcastDesign, string> = { classic: CITRON, bold: CITRON, minimal: CITRON, accent_band: CITRON, photo_header: SKY, letter: CITRON };
export const DESIGN_LABELS: Record<BroadcastDesign, { label: string; hint: string }> = {
  classic: { label: "Classic", hint: "Top rule in Maker Teal" },
  bold: { label: "Bold", hint: "Framed in Workshop Orange" },
  minimal: { label: "Minimal", hint: "A quiet closing line" },
  accent_band: { label: "Accent band", hint: "Title on a solid brand band" },
  photo_header: { label: "Photo header", hint: "The event cover photo on top" },
  letter: { label: "Letter", hint: "Personal note, signed by the organiser" },
};

function Sample({ design, dark }: { design: BroadcastDesign; dark: boolean }) {
  const paper = dark ? INK : CREAM, ink = dark ? CREAM : INK, accent = dark ? DARK[design] : LIGHT[design];
  const line = (width: string): CSSProperties => ({ background: `rgb(${ink} / 0.35)`, width, height: 4, borderRadius: 2 });
  const head: CSSProperties = design === "accent_band" ? { background: `rgb(${accent})`, height: 14, borderRadius: 4 }
    : design === "photo_header" ? { background: `rgb(${accent})`, height: 18, borderRadius: 4 }
    : design === "classic" ? { borderTop: `3px solid rgb(${accent})` } : {};
  const frame: CSSProperties = design === "bold" ? { outline: `2px solid rgb(${accent})`, outlineOffset: -2 } : {};
  return <span aria-hidden="true" className="grid h-16 flex-1 content-start gap-1 rounded-lg p-2" style={{ background: `rgb(${paper})`, ...frame }}>
    <span style={head} />
    <span style={line("70%")} /><span style={line("90%")} /><span style={line("55%")} />
    {design === "minimal" || design === "letter" ? <span style={{ borderTop: `1px solid rgb(${accent})`, marginTop: 2 }} /> : null}
  </span>;
}

const BASE: readonly BroadcastDesign[] = ["classic", "bold", "minimal"];

/** `extended` (events.broadcast_templates on) adds the accent-band, photo-header and letter designs. */
export function BroadcastDesignPicker({ value, extended, onChange }: { value: BroadcastDesign; extended: boolean; onChange: (design: BroadcastDesign) => void }) {
  const designs = extended ? BROADCAST_DESIGNS : BROADCAST_DESIGNS.filter(design => BASE.includes(design) || design === value);
  return <fieldset className="grid gap-2"><legend className="mb-2 text-sm font-semibold">Brand design</legend>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{designs.map(design => <label key={design} className={`grid cursor-pointer gap-2 rounded-2xl border p-3 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-brand ${value === design ? "border-brand bg-brand-soft" : "border-line bg-panel"}`}>
      <span className="flex items-center gap-2"><input type="radio" name="broadcast-design" value={design} checked={value === design} onChange={() => onChange(design)} /><span className="font-semibold">{DESIGN_LABELS[design].label}</span></span>
      <span className="flex gap-2"><Sample design={design} dark={false} /><Sample design={design} dark /></span>
      <span className="text-xs text-muted">{DESIGN_LABELS[design].hint} · light and dark</span>
    </label>)}</div>
  </fieldset>;
}
