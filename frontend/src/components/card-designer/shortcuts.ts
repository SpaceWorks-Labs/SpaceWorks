import { t } from "@lingui/core/macro";

import type { StackOp } from "./stacking";
// The designer's keyboard shortcuts, as a pure mapping from a key event to a command so the
// window listener stays small and the rules are testable. Nothing fires while typing in a field.
export type DesignerCommand =
  | { type: "undo" } | { type: "redo" } | { type: "selectAll" } | { type: "group" } | { type: "ungroup" }
  | { type: "duplicate" } | { type: "copy" } | { type: "paste" } | { type: "delete" } | { type: "clear" }
  | { type: "help" } | { type: "nudge"; dx: number; dy: number } | { type: "resize"; dw: number; dh: number }
  | { type: "stack"; op: StackOp } | { type: "toggle"; flag: "locked" | "hidden" } | { type: "zoom"; to: "in" | "out" | "fit" };

type KeyLike = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey"> & { target: EventTarget | null };

const ARROWS: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };

export function isTypingTarget(target: EventTarget | null) {
  const element = target as HTMLElement | null;
  return Boolean(element?.closest?.("input, textarea, select, [contenteditable='true'], [role='dialog'], [role='menu']"));
}

function modified(key: string, shift: boolean): DesignerCommand | null {
  if (key === "z") return { type: shift ? "redo" : "undo" };
  if (key === "y") return { type: "redo" };
  if (key === "a") return { type: "selectAll" };
  if (key === "g") return { type: shift ? "ungroup" : "group" };
  if (key === "d") return { type: "duplicate" };
  if (key === "c" && !shift) return { type: "copy" };
  if (key === "v" && !shift) return { type: "paste" };
  // Shift turns ] and [ into } and { on most layouts.
  if (key === "]" || key === "}") return { type: "stack", op: shift || key === "}" ? "front" : "forward" };
  if (key === "[" || key === "{") return { type: "stack", op: shift || key === "{" ? "back" : "backward" };
  if (key === "l" && shift) return { type: "toggle", flag: "locked" };
  if (key === "h" && shift) return { type: "toggle", flag: "hidden" };
  if (key === "=" || key === "+") return { type: "zoom", to: "in" };
  if (key === "-" || key === "_") return { type: "zoom", to: "out" };
  if (key === "0") return { type: "zoom", to: "fit" };
  return null;
}

export function designerCommand(event: KeyLike): DesignerCommand | null {
  if (isTypingTarget(event.target)) return null;
  const mod = event.ctrlKey || event.metaKey;
  const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
  if (mod && !event.altKey) return modified(key, event.shiftKey);
  if (mod) return null;
  const arrow = ARROWS[event.key];
  if (arrow) {
    const step = event.shiftKey ? 5 : 1;
    return event.altKey ? { type: "resize", dw: arrow[0] * step, dh: arrow[1] * step }
      : { type: "nudge", dx: arrow[0] * step, dy: arrow[1] * step };
  }
  if (event.key === "Delete" || event.key === "Backspace") return { type: "delete" };
  if (event.key === "Escape") return { type: "clear" };
  if (event.key === "?") return { type: "help" };
  return null;
}

export type ShortcutGroup = { title: string; rows: { keys: string[]; action: string }[] };

/** The list shown in the Keyboard shortcuts dialog (and the docs). A function, so it follows the language switch. */
export function shortcutGroups(): ShortcutGroup[] {
  const mod = t`Ctrl or Cmd`;
  return [
    { title: t`Select`, rows: [
      { keys: [t`Click`], action: t`Select a layer (a grouped layer selects its group)` },
      { keys: ["Shift", t`Click`], action: t`Add to or take from the selection (Ctrl or Cmd works too)` },
      { keys: ["Alt", t`Click`], action: t`Select one layer inside a group` },
      { keys: [mod, "A"], action: t`Select every layer on this side` },
      { keys: ["Esc"], action: t`Clear the selection` },
      { keys: [t`Drag on the card`], action: t`Draw a box to select every layer it touches (Shift adds)` },
      { keys: ["Tab"], action: t`Move through the layers on the card; the Layers list is the keyboard alternative` },
    ] },
    { title: t`View`, rows: [
      { keys: [mod, "+"], action: t`Zoom in` },
      { keys: [mod, "-"], action: t`Zoom out` },
      { keys: [mod, "0"], action: t`Fit the card to the window` },
      { keys: [mod, t`Wheel`], action: t`Zoom the card in and out (pinch works on touch screens)` },
    ] },
    { title: t`Arrange`, rows: [
      { keys: [mod, "]"], action: t`Bring forward` },
      { keys: [mod, "["], action: t`Send backward` },
      { keys: ["Shift", mod, "]"], action: t`Bring to front` },
      { keys: ["Shift", mod, "["], action: t`Send to back` },
      { keys: ["Shift", mod, "L"], action: t`Lock or unlock the selection` },
      { keys: ["Shift", mod, "H"], action: t`Hide or show the selection` },
      { keys: ["Alt", t`Up or Down`], action: t`In the Layers list, move the layer up or down the stack` },
    ] },
    { title: t`Move and size`, rows: [
      { keys: [t`Arrows`], action: t`Move 1 mm (with Shift, 5 mm)` },
      { keys: ["Alt", t`Arrows`], action: t`Resize 1 mm (with Shift, 5 mm)` },
      { keys: ["Alt", t`Drag`], action: t`Move without snapping` },
      { keys: ["Shift", t`Drag corner`], action: t`Keep the shape (photos, images and logos keep it unless Shift is held)` },
      { keys: ["Shift", t`Drag rotate`], action: t`Turn in 15° steps` },
    ] },
    { title: t`Edit`, rows: [
      { keys: [mod, "C"], action: t`Copy the selection` },
      { keys: [mod, "V"], action: t`Paste, also onto the other side` },
      { keys: [mod, "D"], action: t`Duplicate the selection` },
      { keys: [mod, "G"], action: t`Group the selection` },
      { keys: ["Shift", mod, "G"], action: t`Ungroup` },
      { keys: ["Delete"], action: t`Delete the selection (locked layers stay)` },
      { keys: [mod, "Z"], action: t`Undo` },
      { keys: ["Shift", mod, "Z"], action: t`Redo` },
      { keys: ["?"], action: t`Show these shortcuts` },
    ] },
  ];
}
