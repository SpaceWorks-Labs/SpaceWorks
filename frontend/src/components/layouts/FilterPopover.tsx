import { t } from "@lingui/core/macro";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { SlidersHorizontal, X } from "lucide-react";
import { usePresence } from "../../lib/motion";
import { Modal } from "../ui";
import { useLayoutMedia } from "./useLayoutMedia";

export function FilterPopover({ children, count = 0, onClear }: { children: ReactNode; count?: number; onClear?: () => void }) {
  const [open, setOpen] = useState(false);
  const [alignStart, setAlignStart] = useState(false);
  const desktop = useLayoutMedia("(min-width: 768px)");
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const id = useId();
  const presence = usePresence(open && desktop);
  const close = () => { setOpen(false); trigger.current?.focus(); };
  useEffect(() => {
    if (!open || !desktop) return;
    panel.current?.querySelector<HTMLElement>("input,select,button")?.focus();
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open, desktop]);
  const fields = <div className="grid gap-4 [&_.desk-input]:h-11">{children}</div>;
  return <div className="relative" ref={root} onKeyDown={event => {
    if (event.key === "Escape") { event.preventDefault(); close(); }
  }}>
    <button type="button" ref={trigger} className="desk-button h-11 gap-2" aria-haspopup="dialog"
      aria-expanded={open} aria-controls={open ? id : undefined} aria-label={count > 0 ? t`Filters, ${count} active` : t`Filters`} onClick={() => {
        // Opens rightwards when the button sits near the left edge, so the panel never leaves the screen.
        if (!open) setAlignStart((trigger.current?.getBoundingClientRect().right ?? Infinity) < 336);
        setOpen(!open);
      }}>
      <SlidersHorizontal aria-hidden="true" className="size-4" />{t`Filters`}{count > 0 ? <span aria-hidden="true" className="rounded-full bg-emphasis px-2 py-0.5 text-xs font-semibold tabular-nums text-on-emphasis">{count}</span> : null}
    </button>
    {presence.present ? <div ref={panel} id={id} role="dialog" aria-label={t`Filters`} data-state={presence.state} onAnimationEnd={presence.onAnimationEnd} inert={presence.closing}
      className={`sw-fx-menu absolute ${alignStart ? "left-0" : "right-0"} z-30 mt-2 max-h-[70dvh] w-80 max-w-[calc(100vw-2rem)] overflow-y-auto overscroll-contain rounded-2xl border border-line bg-panel p-4 shadow-overlay`}>
      <div className="mb-4 flex items-center justify-between"><span className="font-semibold">{t`Filters`}</span>
        <button type="button" className="desk-button-ghost min-h-11 min-w-11" aria-label={t`Close filters`} onClick={close}><X aria-hidden="true" className="size-4" /></button></div>
      {fields}
      <div className="mt-4 flex justify-end gap-2">{onClear ? <button type="button" className="desk-button" onClick={onClear}>{t`Clear filters`}</button> : null}
        <button type="button" className="desk-button-primary" onClick={close}>{t`Show results`}</button></div>
    </div> : null}
    <Modal open={open && !desktop} onClose={close} title={t`Filters`}
      footer={<div className="flex flex-wrap justify-end gap-2">{onClear ? <button type="button" className="desk-button" onClick={onClear}>{t`Clear filters`}</button> : null}<button type="button" className="desk-button-primary" onClick={close}>{t`Show results`}</button></div>}>{fields}</Modal>
  </div>;
}
