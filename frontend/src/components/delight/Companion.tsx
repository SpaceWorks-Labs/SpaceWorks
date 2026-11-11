import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { DelightArt } from "./Artwork";
import { useDelight, useReducedMotion } from "./DelightProvider";

export function Companion() {
  const [on, setOn] = useState(false);
  const [pose, setPose] = useState<"companionWalk" | "companionFollow" | "companionNap" | "companionPrint">("companionWalk");
  const [position, setPosition] = useState(50);
  const { enabled } = useDelight();
  const reduced = useReducedMotion();
  useEffect(() => {
    if (!on || !enabled || reduced) return;
    const nap = window.setTimeout(() => setPose("companionNap"), 6000);
    return () => window.clearTimeout(nap);
  }, [on, enabled, reduced, pose, position]);
  if (!enabled) return null;
  return <div className="grid gap-3">
    <button type="button" className="desk-button" aria-pressed={on} onClick={() => { setOn(!on); setPose("companionWalk"); }}>{on ? t`Workshop companion: on` : t`Workshop companion: off`}</button>
    {on ? <><div className="relative h-20 overflow-hidden" onPointerMove={event => {
      if (reduced) return;
      const bounds = event.currentTarget.getBoundingClientRect();
      setPosition(Math.max(0, Math.min(80, (event.clientX - bounds.left) / Math.max(1, bounds.width) * 100)));
      setPose("companionFollow");
    }}><span aria-hidden="true" className={`pointer-events-none absolute h-16 w-16 ${!reduced && pose === "companionWalk" ? "sw-delight-walk" : ""}`} style={{ left: `${reduced ? 50 : position}%` }}>
      <DelightArt name={reduced && pose !== "companionPrint" ? "companionNap" : pose} className="h-16 w-16" /></span></div>
      <button type="button" className="desk-button" onClick={() => setPose("companionPrint")}>{t`Print a tiny layer stack`}</button>
      <span className="sr-only" role="status">{pose === "companionPrint" ? t`The workshop companion printed a tiny layer stack.` : ""}</span></> : null}
  </div>;
}
