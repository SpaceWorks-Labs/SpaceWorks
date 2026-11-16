import { t } from "@lingui/core/macro";
import { useEffect, useId, useRef, useState } from "react";
import { usePresence } from "../../lib/motion";
import { ConfirmDialog } from "./ConfirmDialog";
import { RouteLink } from "./RouteLink";
import { Icon } from "./icon";
import type { Action } from "./types";
import { rove, rovingItems } from "./useRovingFocus";
export type OverflowMenuProps = { actions: Action[]; label?: string; className?: string; mobileActions?: Action[]; showLabel?: boolean };
export function OverflowMenu({ actions, label = t`More actions`, className = "", mobileActions = [], showLabel = false }: OverflowMenuProps) {
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState<Action | null>(null);
  // A trigger near the left edge (a wrapped phone header row) opens its menu rightwards, never off-screen.
  const [alignStart, setAlignStart] = useState(false);
  const toggle = (next: boolean) => {
    if (next) setAlignStart((trigger.current?.getBoundingClientRect().right ?? Infinity) < 272);
    setOpen(next);
  };
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const focusLast = useRef(false);
  const id = useId();
  const presence = usePresence(open);
  const close = (restore = false) => { setOpen(false); if (restore) trigger.current?.focus(); };
  useEffect(() => {
    if (!open) return;
    const visible = menu.current ? rovingItems(menu.current, '[role="menuitem"]') : [];
    (focusLast.current ? visible[visible.length - 1] : visible[0])?.focus();
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  const item = (action: Action, index: number, mobile: boolean) => {
    const disabled = action.disabled || action.pending;
    const text = action.pending ? action.pendingLabel ?? t`Working…` : `${action.label}${action.confirms && !action.label.endsWith("…") ? "…" : ""}`;
    const classes = `flex min-h-11 w-full items-center gap-2 rounded-control px-3 py-2 text-left text-sm hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${disabled ? "cursor-not-allowed bg-surface text-muted" : action.tone === "danger" ? "text-danger" : "text-ink"}`;
    const content = <>{action.icon ? <Icon name={action.icon} /> : null}{text}{action.disabledReason ? <span className="sr-only"> · {action.disabledReason}</span> : null}</>;
    const click = () => { if (!disabled) { close(true); if (action.confirm) setConfirming(action); else action.onClick?.(); } };
    return <div role="none" key={`${mobile}-${action.label}-${action.href ?? ""}-${index}`} className={mobile ? "md:hidden" : undefined}>
      {action.href ? <RouteLink role="menuitem" tabIndex={-1} aria-disabled={disabled || undefined} aria-busy={action.pending || undefined} href={disabled ? undefined : action.href}
        target={action.external ? "_blank" : undefined} rel={action.external ? "noopener noreferrer" : undefined}
        className={classes} onClick={click}>{content}</RouteLink>
        : <button role="menuitem" type="button" tabIndex={-1} aria-disabled={disabled || undefined} aria-busy={action.pending || undefined}
          className={classes} onClick={click}>{content}</button>}
    </div>;
  };
  if (!actions.length && !mobileActions.length) return null;
  const dialog = confirming?.confirm ? <ConfirmDialog open title={confirming.confirm.title} message={confirming.confirm.message}
    confirmLabel={confirming.confirm.confirmLabel ?? confirming.label} tone={confirming.tone === "danger" ? "danger" : "default"}
    onCancel={() => setConfirming(null)} onConfirm={() => { const run = confirming.onClick; setConfirming(null); run?.(); }} /> : null;
  return <div ref={root} className={`relative ${className}`} onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget as Node)) setOpen(false);
  }}>
    <button ref={trigger} type="button" className="desk-button min-w-11 gap-2"
      aria-label={label} aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined}
      onClick={() => { focusLast.current = false; toggle(!open); }}
      onKeyDown={event => {
        if (["ArrowDown", "ArrowUp"].includes(event.key)) {
          event.preventDefault(); focusLast.current = event.key === "ArrowUp"; toggle(true);
        }
      }}>{showLabel ? <>{label}<Icon name="ChevronDown" /></> : <Icon name="Ellipsis" />}</button>
    {presence.present ? <div id={id} ref={menu} role="menu" aria-label={label} data-state={presence.state} onAnimationEnd={presence.onAnimationEnd} inert={presence.closing}
      className={`sw-fx-menu absolute ${alignStart ? "left-0" : "right-0"} z-30 mt-2 max-h-[min(60dvh,28rem)] w-64 max-w-[calc(100vw-2rem)] overflow-y-auto overscroll-contain rounded-xl border border-line bg-panel p-1 shadow-overlay`}
      onKeyDown={event => {
        if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); close(true); }
        else if (event.key === "Tab") close(true);
        else if (event.key === " ") { event.preventDefault(); (document.activeElement as HTMLElement)?.click(); }
        else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey && event.key !== " ") {
          const items = rovingItems(event.currentTarget, '[role="menuitem"]');
          const current = items.indexOf(document.activeElement as HTMLElement);
          const next = [...items.slice(current + 1), ...items.slice(0, current + 1)]
            .find(item => item.textContent?.trim().toLocaleLowerCase().startsWith(event.key.toLocaleLowerCase()));
          if (next) { event.preventDefault(); next.focus(); }
        } else rove(event, '[role="menuitem"]');
      }}>
      {mobileActions.map((action, i) => item(action, i, true))}
      {actions.map((action, i) => item(action, i, false))}
    </div> : null}
    {dialog}
  </div>;
}
