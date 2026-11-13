// What sits AROUND the card on the canvas: millimetre rulers along the top and left edges (click one to drop a
// guide line there) and the bleed band outside the trim. Editor-only; nothing here prints except that a
// print-ready export runs the card's edges on into that band (print_export.py, mirror bleed).
import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";

export const RULER_PX = 20;
const TICK = "#7A8582";

function Ruler({ axis, lengthMm, px, onPick }: { axis: "x" | "y"; lengthMm: number; px: number; onPick?: (atMm: number) => void }) {
  const length = lengthMm * px;
  const step = px >= 6 ? 1 : px >= 3 ? 2 : 5;
  const ticks = [];
  for (let mm = 0; mm <= lengthMm + 0.001; mm += step) {
    const major = mm % 10 === 0, mid = mm % 5 === 0;
    const size = major ? RULER_PX * 0.6 : mid ? RULER_PX * 0.4 : RULER_PX * 0.22;
    const at = mm * px;
    ticks.push(axis === "x"
      ? <line key={mm} x1={at} x2={at} y1={RULER_PX} y2={RULER_PX - size} stroke={TICK} strokeWidth={1} />
      : <line key={mm} y1={at} y2={at} x1={RULER_PX} x2={RULER_PX - size} stroke={TICK} strokeWidth={1} />);
    if (major && mm > 0 && px * 10 >= 24) {
      ticks.push(axis === "x"
        ? <text key={`n${mm}`} x={at + 2} y={9} fontSize={9} fill={TICK}>{mm}</text>
        : <text key={`n${mm}`} x={2} y={at - 2} fontSize={9} fill={TICK}>{mm}</text>);
    }
  }
  const pick = (event: React.MouseEvent<SVGSVGElement>) => {
    if (!onPick) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const offset = axis === "x" ? event.clientX - rect.left : event.clientY - rect.top;
    onPick(Math.round(offset / px * 2) / 2);
  };
  return <svg aria-hidden="true" width={axis === "x" ? length : RULER_PX} height={axis === "x" ? RULER_PX : length}
    className={`absolute overflow-visible ${onPick ? "cursor-copy" : ""}`} onClick={pick}
    style={axis === "x" ? { left: RULER_PX, top: 0 } : { left: 0, top: RULER_PX }}>{ticks}</svg>;
}

/** Wraps the card surface. `bleedMm` > 0 draws the bleed band outside the trim; `rulers` adds the edge rulers. */
export function CanvasFrame({ widthMm, heightMm, px, bleedMm, rulers, onAddGuide, children }: {
  widthMm: number; heightMm: number; px: number; bleedMm: number; rulers: boolean;
  onAddGuide?: (axis: "x" | "y", atMm: number) => void; children: ReactNode;
}) {
  const bleed = Math.max(0, bleedMm) * px;
  const offset = rulers ? RULER_PX : 0;
  const pad = Math.max(bleed, rulers ? 4 : 0);
  return <div className="relative mx-auto" style={{ width: widthMm * px + offset + 2 * pad, height: heightMm * px + offset + 2 * pad }}>
    {rulers ? <>
      <span aria-hidden="true" className="absolute left-0 top-0 rounded-sm bg-surface" style={{ width: RULER_PX, height: RULER_PX }} />
      <div className="absolute" style={{ left: pad, top: 0 }}>
        <Ruler axis="x" lengthMm={widthMm} px={px} onPick={onAddGuide ? (at) => onAddGuide("x", at) : undefined} /></div>
      <div className="absolute" style={{ left: 0, top: pad }}>
        <Ruler axis="y" lengthMm={heightMm} px={px} onPick={onAddGuide ? (at) => onAddGuide("y", at) : undefined} /></div>
    </> : null}
    <div className="absolute" style={{ left: offset + pad, top: offset + pad }}>
      {bleed > 0 ? <div aria-hidden="true" title={t`Bleed: the card's edges run on to here in a print-ready export`}
        className="pointer-events-none absolute border border-dashed"
        style={{ left: -bleed, top: -bleed, width: widthMm * px + 2 * bleed, height: heightMm * px + 2 * bleed,
          borderColor: "#BE123C", background: "rgba(190,18,60,0.10)" }} /> : null}
      {children}
    </div>
  </div>;
}
