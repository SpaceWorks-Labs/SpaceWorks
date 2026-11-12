// Binds the designer shortcuts (shortcuts.ts) on the window, but only for key presses that
// happen inside the designer (or with nothing focused), never while typing or in a dialog.
// Arrow keys act only when focus is on the canvas, so menus and radio groups keep their arrows.
import { useEffect, useRef, type RefObject } from "react";

import { designerCommand, type DesignerCommand } from "./shortcuts";
import type { DesignerEditing } from "./useDesignerEditing";

type Handlers = { editing: DesignerEditing; selection: string[]; undo: () => void; redo: () => void; help: () => void;
  /** Zoom the canvas (Ctrl/Cmd + plus, minus, 0); absent where the view has no zoom. */ zoom?: (to: "in" | "out" | "fit") => void };

/** Run one command; returns whether the designer used the key (so the browser default is cancelled). */
export function runCommand(command: DesignerCommand, { editing, selection, undo, redo, help, zoom }: Handlers, onCanvas: boolean) {
  const any = selection.length > 0;
  const edit = editing.canEdit;
  switch (command.type) {
    case "undo": if (edit) undo(); return edit;
    case "redo": if (edit) redo(); return edit;
    case "selectAll": editing.selectAll(); return true;
    case "clear": if (any) editing.clear(); return any;
    case "help": help(); return true;
    case "copy": {
      if (!any || window.getSelection?.()?.toString()) return false;
      editing.copy(); return true;
    }
    case "paste": if (!edit || !editing.canPaste()) return false; editing.paste(); return true;
    case "group": if (edit && selection.length > 1) editing.group(); return edit && any;
    case "ungroup": if (edit && any) editing.ungroup(); return edit && any;
    case "duplicate": if (edit && any) editing.duplicate(); return edit && any;
    case "delete": if (edit && any) editing.remove(); return edit && any;
    case "nudge": if (!onCanvas || !edit || !any) return false; editing.nudge(command.dx, command.dy); return true;
    case "resize": if (!onCanvas || !edit || !any) return false; editing.resizeBy(command.dw, command.dh); return true;
    case "stack": if (edit && any) editing.restack(command.op); return edit && any;
    case "toggle": if (edit && any) editing.toggleFlag(command.flag); return edit && any;
    case "zoom": if (!zoom) return false; zoom(command.to); return true;
  }
}

export function useDesignerKeys(scope: RefObject<HTMLElement | null>, handlers: Handlers) {
  const latest = useRef(handlers);
  latest.current = handlers;
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.defaultPrevented) return;
      const target = event.target as HTMLElement | null;
      const inside = target === window.document.body || (target && scope.current?.contains(target));
      if (!inside) return;
      const command = designerCommand(event);
      if (!command) return;
      const onCanvas = target === window.document.body || Boolean(target?.closest?.("[data-card-canvas], [data-card-viewport]"));
      if (runCommand(command, latest.current, onCanvas)) event.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [scope]);
}
