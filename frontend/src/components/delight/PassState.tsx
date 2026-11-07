import { formatLocale } from "../../lib/format";
import { useEffect, useRef, type ReactNode } from "react";
import { Check, Clock } from "lucide-react";
import { useDelight, useReducedMotion } from "./DelightProvider";
import "./delight.css";

export type PersistedPassState = { state: "ready"; label: string } | { state: "completed"; label: string; completedAt: string };
export function safeHaptic() {
  try { navigator.vibrate?.([35, 60, 70]); } catch { /* Optional device feedback never affects workflow. */ }
}

/** completedAt must come from the persisted workflow, never a pending mutation. */
export function PassState({ value, title, children, haptics = false, accent = true }: {
  value: PersistedPassState; title: string; children?: ReactNode; haptics?: boolean; accent?: boolean;
}) {
  const { enabled } = useDelight();
  const reduced = useReducedMotion();
  const completed = value.state === "completed";
  const identity = completed ? value.completedAt : null;
  const previous = useRef(identity);
  const changed = previous.current !== identity;
  useEffect(() => {
    if (identity !== previous.current && identity && enabled && haptics) safeHaptic();
    previous.current = identity;
  }, [identity, enabled, haptics]);
  return <section aria-label={title} className="rounded-2xl border border-line bg-panel text-ink">
    <div className="grid gap-3 p-5"><h2 className="title-section">{title}</h2>{children}</div>
    <div key={identity} className={`flex items-center gap-3 border-t border-dashed border-line p-5 ${completed && enabled && !reduced && changed ? "sw-delight-pass" : ""}`}>
      {completed ? <Check aria-hidden="true" size={20} /> : <Clock aria-hidden="true" size={20} />}
      <div><p className={accent ? "font-accent text-lg font-medium" : "font-medium"} aria-live="polite" aria-atomic="true">{value.label}</p>
        {completed ? <time className="text-sm text-muted" dateTime={value.completedAt}>{new Date(value.completedAt).toLocaleString(formatLocale())}</time> : null}</div>
    </div>
  </section>;
}
