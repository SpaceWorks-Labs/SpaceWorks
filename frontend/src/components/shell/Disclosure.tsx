import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { usePresence } from "../../lib/motion";
import { focusRing } from "./types";

// A disclosure keeps ordinary button/link semantics and normal Tab navigation.
export function Disclosure({ label, children, above = false }: { label: ReactNode; children: ReactNode; above?: boolean }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const presence = usePresence(open);
  const location = useLocation();
  useEffect(() => { setOpen(false); }, [location]);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false); };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  return <div ref={root} className="relative min-w-0" onBlur={event => { if (open && !event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false); }}
    onKeyDown={event => {
    if (event.key === "Escape" && open) { event.preventDefault(); event.stopPropagation(); setOpen(false); trigger.current?.focus(); }
  }}>
    <button ref={trigger} type="button" aria-expanded={open} aria-controls={id}
      className={`flex min-h-11 w-full items-center gap-2 rounded-xl border border-outline bg-panel p-2 text-left text-ink ${focusRing}`}
      onClick={() => setOpen(!open)}>{label}</button>
    {presence.present ? <div id={id} data-state={presence.state} data-above={above ? "" : undefined} onAnimationEnd={presence.onAnimationEnd} inert={presence.closing} className={`sw-fx-menu absolute right-0 z-40 w-60 max-w-[calc(100vw-2rem)] max-h-[50dvh] overflow-y-auto rounded-xl border border-line bg-panel p-2 shadow-overlay ${above ? "bottom-full mb-2" : "top-full mt-2"}`}
      onClick={event => { if ((event.target as HTMLElement).closest("a,button")) { setOpen(false); trigger.current?.focus(); } }}>{children}</div> : null}
  </div>;
}
