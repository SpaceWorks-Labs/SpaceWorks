// Undo/redo shared by the card designer and the event badge designer (SPEC §10, parity item 13):
// whole-document snapshots (50 by default) and the same keyboard shortcuts everywhere --
// Ctrl/Cmd+Z undoes, Shift+Ctrl/Cmd+Z or Ctrl/Cmd+Y redoes -- ignored while typing in a field.
import { useCallback, useEffect, useRef, useState } from "react";

export const HISTORY_LIMIT = 50;

export function undoShortcut(event: KeyboardEvent): "undo" | "redo" | null {
  const target = event.target as HTMLElement | null;
  if (target?.closest?.("input, textarea, select, [contenteditable='true']")) return null;
  if (!(event.metaKey || event.ctrlKey)) return null;
  const key = event.key.toLowerCase();
  if (key === "z") return event.shiftKey ? "redo" : "undo";
  return key === "y" ? "redo" : null;
}

/** History for a controlled value: call `record(previous)` before each change; `apply` sets the value. */
export function useUndoHistory<T>(current: T, apply: (value: T) => void, limit = HISTORY_LIMIT) {
  const [past, setPast] = useState<T[]>([]);
  const [future, setFuture] = useState<T[]>([]);
  const record = useCallback((previous: T) => {
    setPast((stack) => [...stack.slice(-(limit - 1)), previous]);
    setFuture([]);
  }, [limit]);
  // Stacks are read from state and changed outside updaters so StrictMode never pushes twice.
  const undo = useCallback(() => {
    const previous = past[past.length - 1];
    if (previous === undefined) return;
    setPast(past.slice(0, -1));
    setFuture([...future, current]);
    apply(previous);
  }, [past, future, current, apply]);
  const redo = useCallback(() => {
    const next = future[future.length - 1];
    if (next === undefined) return;
    setFuture(future.slice(0, -1));
    setPast([...past.slice(-(limit - 1)), current]);
    apply(next);
  }, [past, future, current, apply, limit]);
  return { record, undo, redo, canUndo: past.length > 0, canRedo: future.length > 0 };
}

/** Bind the shared shortcuts on the window while `enabled`. */
export function useUndoShortcuts(undo: () => void, redo: () => void, enabled = true) {
  const handlers = useRef({ undo, redo });
  handlers.current = { undo, redo };
  useEffect(() => {
    if (!enabled) return;
    function onKey(event: KeyboardEvent) {
      const action = undoShortcut(event);
      if (!action) return;
      event.preventDefault();
      handlers.current[action]();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled]);
}
