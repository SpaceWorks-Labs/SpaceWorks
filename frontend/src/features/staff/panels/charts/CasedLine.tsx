import { edge } from "./chartStyle";

/** A 2px bright line over a 4px edge casing; the dash pattern stays on both so colour is never the only cue. */
export function CasedLine({ points, color, dash }: { points: string; color: string; dash?: string }) {
  return <>
    <polyline points={points} fill="none" stroke={edge} strokeWidth="4" strokeDasharray={dash || undefined} strokeLinejoin="round" />
    <polyline points={points} fill="none" stroke={color} strokeWidth="2" strokeDasharray={dash || undefined} strokeLinejoin="round" />
  </>;
}
