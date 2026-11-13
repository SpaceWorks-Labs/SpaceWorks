import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { useEffect, useId, useRef, useSyncExternalStore } from "react";
import {
  consumePendingRestore,
  focusFirstDialogElement,
  getSnapshot,
  popDialog,
  pushDialog,
  subscribe,
  trapDialogFocus,
} from "./dialogFocus";
import { usePresence } from "../../lib/motion";
import { revealFieldAboveKeyboard } from "./keyboardSafe";
import { OverlayPortal } from "./OverlayPortal";

export type DetailDrawerProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Which edge the panel slides from; the phone navigation drawer uses "left". */
  edge?: "right" | "left";
};

export function DetailDrawer({ open, title, onClose, children, edge = "right" }: DetailDrawerProps) {
  const titleId = useId();
  const presence = usePresence(open, 180);
  const layerRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  const tokenRef = useRef<symbol | null>(null);
  const top = useSyncExternalStore(subscribe, getSnapshot);
  const amTop = top === tokenRef.current;
  const amTopRef = useRef(amTop);
  amTopRef.current = amTop;
  // See Modal.tsx: onClose lives in a ref so this focus effect depends only on `open`.
  // Otherwise a fresh inline onClose each render re-runs the effect and steals focus.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const token = pushDialog({
      previousFocus,
      getPanel: () => panelRef.current,
      getLayer: () => layerRef.current,
    });
    tokenRef.current = token;
    const panel = panelRef.current;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!amTopRef.current) return;
      if (event.key === "Escape" && !event.defaultPrevented) onCloseRef.current();
      if (panel) trapDialogFocus(event, panel);
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      popDialog(token);
      if (tokenRef.current === token) tokenRef.current = null;
    };
  }, [open]);

  useEffect(() => {
    if (!amTop) return;
    consumePendingRestore(panelRef.current);
    // Initial focus lives HERE, not in the push effect. A dialog that opens while another sits
    // above it renders with `inert` on its layer, and `inert` is only cleared by the re-render
    // that follows becoming topmost -- so focusing from the push effect silently fails, and
    // consumePendingRestore no-ops because nothing was popped. This effect runs post-commit,
    // once `inert` is gone. jsdom implements no `inert` at all, so no unit test can catch this.
    const panel = panelRef.current;
    if (panel && !panel.contains(document.activeElement)) focusFirstDialogElement(panel);
  }, [amTop]);

  if (!presence.present) return null;

  return (
    <OverlayPortal>
    <div ref={layerRef} inert={!amTop || presence.closing} className="sw-overlay-layer fixed inset-0 z-50">
      <button
        type="button"
        aria-label={t`Close detail drawer`}
        data-state={presence.state}
        className="sw-fx-fade absolute inset-0 bg-scrim/30"
        onClick={onClose}
      />
      <aside
        aria-modal={amTop ? "true" : undefined}
        role="dialog"
        aria-labelledby={titleId}
        ref={panelRef}
        data-state={presence.state}
        data-edge={edge}
        onAnimationEnd={presence.onAnimationEnd}
        tabIndex={-1}
        /* `max-w-xl` (576px) was too narrow for the content this holds: the machine drawer's
           tab row and its two-column forms both overflowed, so tabs were clipped mid-word and
           an "Add" button sat half outside the panel. Widened, and capped at the viewport so
           it can never exceed the screen on a small display. */
        className="sw-fx-drawer absolute right-0 top-0 flex h-full w-full md:max-w-[min(48rem,100vw)] flex-col border-l border-line bg-panel shadow-overlay focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      >
        {/* Full screen on phones, so the header and body pad for the notch and home indicator. */}
        <header className="flex shrink-0 items-center gap-3 border-b border-line pt-[max(1rem,env(safe-area-inset-top))] pr-[max(1.25rem,env(safe-area-inset-right))] pb-4 pl-[max(1.25rem,env(safe-area-inset-left))] md:pt-4">
          <h2 id={titleId} className="title-panel min-w-0 truncate" title={title}>
            {title}
          </h2>
          <button type="button" className="desk-button ml-auto shrink-0" onClick={onClose}>
            {t`Close`}</button>
        </header>
        {/* `min-w-0` so a wide child (a table, a long unbroken string) is constrained by the
            drawer and scrolls inside its own container, rather than stretching this flex column
            and pushing content out past the panel edge. */}
        <div className="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain p-5 pr-[max(1.25rem,env(safe-area-inset-right))] pb-[max(1.25rem,env(safe-area-inset-bottom))] pl-[max(1.25rem,env(safe-area-inset-left))]"
          onFocus={revealFieldAboveKeyboard}>{children}</div>
      </aside>
    </div>
    </OverlayPortal>
  );
}
