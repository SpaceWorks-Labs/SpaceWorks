// What the canvas draws over the card while you work: snap guides, equal-spacing hints, the
// box around a multi-selection and the live position/size readout. Decorative (aria-hidden):
// the same numbers are in the inspector for screen readers.
import type { Guide, SpacingHint } from "./canvasMath";
import type { Box } from "./selection";

export type Readout = { box: Box; text: string };
const GUIDE = "#FF7447";

export function CanvasOverlays({ px, guides, hints, bounds, readout }: {
  px: number; guides: Guide[]; hints: SpacingHint[]; bounds: Box | null; readout: Readout | null;
}) {
  return <>
    {bounds ? <span aria-hidden="true" className="pointer-events-none absolute border border-dashed border-accent-ink"
      style={{ left: bounds.x * px - 2, top: bounds.y * px - 2, width: bounds.w * px + 4, height: bounds.h * px + 4 }} /> : null}
    {guides.map((guide, index) => <span key={`g${index}`} aria-hidden="true" className="pointer-events-none absolute"
      style={{ background: GUIDE, ...(guide.axis === "x" ? { left: guide.at * px, top: 0, bottom: 0, width: 1 }
        : { top: guide.at * px, left: 0, right: 0, height: 1 }) }} />)}
    {hints.flatMap((hint, index) => hint.gaps.map(([from, to], gap) => <span key={`h${index}-${gap}`} aria-hidden="true"
      className="pointer-events-none absolute" style={hint.axis === "x"
        ? { left: from * px, width: (to - from) * px, top: hint.cross * px, height: 0, borderTop: `1px solid ${GUIDE}`,
          borderLeft: `1px solid ${GUIDE}`, borderRight: `1px solid ${GUIDE}` }
        : { top: from * px, height: (to - from) * px, left: hint.cross * px, width: 0, borderLeft: `1px solid ${GUIDE}`,
          borderTop: `1px solid ${GUIDE}`, borderBottom: `1px solid ${GUIDE}` }} />))}
    {readout ? <span aria-hidden="true"
      className="pointer-events-none absolute z-10 whitespace-nowrap rounded-control bg-ink px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-panel shadow-overlay"
      style={{ left: Math.max(2, readout.box.x * px),
        top: readout.box.y * px > 26 ? readout.box.y * px - 24 : (readout.box.y + readout.box.h) * px + 4 }}>
      {readout.text}</span> : null}
  </>;
}

export const mm = (value: number) => value.toFixed(1);
