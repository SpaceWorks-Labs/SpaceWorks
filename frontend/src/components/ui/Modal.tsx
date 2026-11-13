import { t } from "@lingui/core/macro";
import type React from "react";
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
import { X } from "lucide-react";

export type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "md" | "xl";
  backdrop?: "plain" | "blur";
};

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  size = "md",
  backdrop = "plain",
}: ModalProps) {
  const titleId = useId();
  const presence = usePresence(open);
  const layerRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const tokenRef = useRef<symbol | null>(null);
  const top = useSyncExternalStore(subscribe, getSnapshot);
  const amTop = top === tokenRef.current;
  const amTopRef = useRef(amTop);
  amTopRef.current = amTop;
  const maxWidthClass = size === "xl" ? "max-w-4xl" : "max-w-lg";
  const backdropClass =
    backdrop === "blur" ? "bg-scrim/35 backdrop-blur-sm" : "bg-scrim/40";
  // Keep onClose in a ref so the focus effect depends only on `open`. Callers pass a
  // fresh inline onClose every render; if it were in the dep array, every keystroke
  // (which re-renders the parent) would re-run this effect and steal focus back to the
  // first field. The ref lets Escape always call the latest onClose without that churn.
  const downOnBackdrop = useRef(false);
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
    <div
      ref={layerRef}
      inert={!amTop || presence.closing}
      data-state={presence.state}
      onAnimationEnd={presence.onAnimationEnd}
      // Phones: a bottom sheet with a safe-area-aware footer. Tablet and up: a centred dialog.
      className={`sw-overlay-layer sw-fx-fade fixed inset-0 z-50 flex items-end justify-center ${backdropClass} pt-[max(0.5rem,env(safe-area-inset-top))] sm:items-center sm:pr-[max(1rem,env(safe-area-inset-right))] sm:pb-4 sm:pl-[max(1rem,env(safe-area-inset-left))]`}
      onMouseDown={(event) => { downOnBackdrop.current = event.target === event.currentTarget; }}
      onClick={(event) => {
        // A text-selection drag that starts in a field and ends on the backdrop must not close the dialog.
        if (downOnBackdrop.current && event.target === event.currentTarget) onClose();
        downOnBackdrop.current = false;
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal={amTop ? "true" : undefined}
        aria-labelledby={titleId}
        tabIndex={-1}
        data-state={presence.state}
        className={`sw-fx-pop desk-panel shadow-overlay relative flex max-h-full w-full ${maxWidthClass} flex-col overflow-hidden rounded-b-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus sm:max-h-[calc(100dvh-2rem)] sm:rounded-b-xl`}
      >
        <div className="shrink-0 border-b border-line py-4 pr-16 pl-[max(1.25rem,env(safe-area-inset-left))] sm:px-5">
          <h2 id={titleId} className="title-panel break-words">
            {title}
          </h2>
        </div>
        <div className={`desk-panel-body min-h-0 min-w-0 overflow-y-auto overflow-x-hidden overscroll-contain p-5 ${footer ? "" : "pb-[max(1.25rem,env(safe-area-inset-bottom))] sm:pb-5"}`}
          onFocus={revealFieldAboveKeyboard}>{children}</div>
        {footer ? <div className="shrink-0 border-t border-line px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:pb-3">{footer}</div> : null}
        {/* Phones get a visible close in the sheet's corner. Last in the DOM so the first field still takes initial focus. */}
        <button type="button" aria-label={t`Close dialog`} onClick={onClose}
          className="desk-button-ghost absolute top-2.5 right-2.5 min-h-11 min-w-11 px-2"><X aria-hidden="true" size={20} /></button>
      </div>
    </div>
    </OverlayPortal>
  );
}
