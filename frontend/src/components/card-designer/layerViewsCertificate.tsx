// Certificate-only layers (spec section 12): signature rows bound to signatory slots, the seal, and the serial.
// Signatories come from the values map (`signatory_<slot>_name` / `_title`); a slot with no name is absent
// and the remaining ones are re-spaced equally, exactly like the server.
import { useId } from "react";

import { PT_TO_MM } from "./cardGeometry";
import type { Layer } from "./cardTypes";
import { canonicalFamily } from "./fontLoader";

export const signatoryName = (values: Record<string, string>, slot: number) => values[`signatory_${slot}_name`] ?? "";
export const signatoryTitle = (values: Record<string, string>, slot: number) => values[`signatory_${slot}_title`] ?? "";

const family = (layer: Layer) => `"SW Card ${canonicalFamily(layer.font_family ?? "Outfit")}", sans-serif`;

/** The fractions of the layer height the server uses: image above 0.56, rule at 0.56, name at 0.60, title at 0.80. */
export const SIGNATURE_FRACTIONS = { rule: 0.56, name: 0.60, title: 0.80 } as const;

function Scribble({ colour }: { colour: string }) {
  return <svg viewBox="0 0 100 30" preserveAspectRatio="xMidYMax meet" className="h-full w-full" aria-hidden="true">
    <path d="M6 22 C14 2 20 4 22 14 C24 24 30 6 38 12 C44 17 40 24 50 14 C58 6 62 20 70 12 C76 6 84 20 94 10"
      fill="none" stroke={colour} strokeWidth="1.6" strokeLinecap="round" />
  </svg>;
}

export function SignatureCell({ layer, slot, px, values, mono }: { layer: Layer; slot: number; px: number;
  values: Record<string, string>; mono: boolean }) {
  const ink = mono ? "#000000" : layer.colour ?? "#142C2A";
  const rule = layer.rule === undefined ? { colour: ink, width_pt: 0.6 } : layer.rule;
  const h = layer.h_mm * px;
  const size = (layer.font_size_pt ?? 10) * PT_TO_MM * px;
  const base = { fontFamily: family(layer), fontWeight: layer.font_weight ?? 400, color: ink, fontSize: size, lineHeight: 1.15,
    textAlign: layer.align ?? "center" as const };
  return <div className="relative h-full w-full">
    {layer.show_image !== false ? <div className="absolute inset-x-0 top-0" style={{ height: h * SIGNATURE_FRACTIONS.rule }}>
      <Scribble colour={ink} /></div> : null}
    {rule ? <div className="absolute inset-x-0" style={{ top: h * SIGNATURE_FRACTIONS.rule,
      borderTop: `${Math.max(1, rule.width_pt * PT_TO_MM * px)}px solid ${mono ? "#000000" : rule.colour}` }} /> : null}
    {layer.show_name !== false ? <div className="absolute inset-x-0 truncate" style={{ ...base, top: h * SIGNATURE_FRACTIONS.name }}>
      {signatoryName(values, slot)}</div> : null}
    {layer.show_title !== false ? <div className="absolute inset-x-0 truncate" style={{ ...base, fontWeight: 300,
      top: h * SIGNATURE_FRACTIONS.title }}>{signatoryTitle(values, slot)}</div> : null}
  </div>;
}

/** One signature (`signatory_slot`) or a row of them (`slots`, gap_mm apart, absent slots skipped and the rest re-spaced). */
export function SignatureLayerView({ layer, px, values, mono }: { layer: Layer; px: number; values: Record<string, string>; mono: boolean }) {
  if (layer.kind === "signature") {
    return <SignatureCell layer={layer} slot={layer.signatory_slot ?? 1} px={px} values={values} mono={mono} />;
  }
  const present = (layer.slots ?? [1, 2]).filter((slot) => signatoryName(values, slot));
  if (!present.length) return null;
  const gap = layer.gap_mm ?? 10;
  const cell = (layer.w_mm - gap * (present.length - 1)) / present.length;
  return <div className="relative h-full w-full">
    {present.map((slot, index) => <div key={slot} className="absolute top-0 h-full"
      style={{ left: index * (cell + gap) * px, width: cell * px }}>
      <SignatureCell layer={layer} slot={slot} px={px} values={values} mono={mono} />
    </div>)}
  </div>;
}

function starPath(cx: number, cy: number, outer: number, inner: number, points: number) {
  return Array.from({ length: points * 2 }, (_v, i) => {
    const angle = (Math.PI * i) / points - Math.PI / 2;
    const r = i % 2 === 0 ? outer : inner;
    return `${i === 0 ? "M" : "L"}${(cx + Math.cos(angle) * r).toFixed(2)} ${(cy + Math.sin(angle) * r).toFixed(2)}`;
  }).join(" ") + " Z";
}

/** A seal: ring, scallop (24-bump rosette) or star (12 points), with a label and Latin ring text set clockwise from the top. */
export function SealLayerView({ layer, px, mono }: { layer: Layer; px: number; mono: boolean }) {
  const id = `r${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const d = Math.min(layer.w_mm, layer.h_mm);
  const c = d / 2;
  const fill = mono ? "#EEEEEE" : layer.fill ?? "#DFFF8F", stroke = mono ? "#000000" : typeof layer.stroke === "string" ? layer.stroke : "#142C2A";
  const sw = layer.stroke_mm ?? 0.5;
  const ringText = (layer.ring_text ?? "").slice(0, 40);
  const textRadius = c * 0.74;
  const style = layer.style ?? "ring";
  const body = style === "star" ? <path d={starPath(c, c, c - sw, c * 0.8, 12)} />
    : style === "scallop" ? <path d={starPath(c, c, c - sw, c * 0.9, 24)} /> : <circle cx={c} cy={c} r={c - sw} />;
  return <svg width={layer.w_mm * px} height={layer.h_mm * px} viewBox={`0 0 ${layer.w_mm} ${layer.h_mm}`}
    preserveAspectRatio="xMidYMid meet" role="img" aria-label={layer.label || undefined} aria-hidden={layer.label ? undefined : true}>
    <g fill={fill} stroke={stroke} strokeWidth={sw} strokeLinejoin="round">{body}</g>
    <circle cx={c} cy={c} r={c * 0.9 - sw} fill="none" stroke={stroke} strokeWidth={sw * 0.6} />
    <circle cx={c} cy={c} r={c * 0.5} fill="none" stroke={stroke} strokeWidth={sw * 0.6} />
    {ringText ? <>
      <path id={id} d={`M ${c - textRadius} ${c} a ${textRadius} ${textRadius} 0 1 1 ${textRadius * 2} 0 a ${textRadius} ${textRadius} 0 1 1 ${-textRadius * 2} 0`}
        fill="none" transform={`rotate(-90 ${c} ${c})`} />
      <text fill={mono ? "#000000" : layer.ring_text_colour ?? stroke} fontFamily={family(layer)} fontWeight={600}
        fontSize={c * 0.17} letterSpacing={c * 0.03}>
        <textPath href={`#${id}`} startOffset="0">{ringText}</textPath></text>
    </> : null}
    {layer.label ? <text x={c} y={c} textAnchor="middle" dominantBaseline="central" fill={mono ? "#000000" : layer.colour ?? stroke}
      fontFamily={family(layer)} fontWeight={layer.font_weight ?? 800} fontSize={Math.min(c * 0.3, (layer.font_size_pt ?? 10) * PT_TO_MM)}>
      {layer.label}</text> : null}
  </svg>;
}

/** The certificate serial: the whole id, or its first eight characters upper-cased. */
export function CertificateIdView({ layer, px, values, mono }: { layer: Layer; px: number; values: Record<string, string>; mono: boolean }) {
  const serial = values.serial ?? "";
  const text = layer.format === "short" ? serial.slice(0, 8).toUpperCase() : serial;
  return <div className="flex h-full w-full items-center overflow-hidden whitespace-nowrap" style={{ fontFamily: family(layer),
    fontWeight: layer.font_weight ?? 400, fontSize: (layer.font_size_pt ?? 8) * PT_TO_MM * px, color: mono ? "#000000" : layer.colour ?? "#142C2A",
    justifyContent: { left: "flex-start", center: "center", right: "flex-end" }[layer.align ?? "left"],
    letterSpacing: (layer.tracking_pt ?? 0) * PT_TO_MM * px }}>{text}</div>;
}
