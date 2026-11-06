// The designer's keyboard shortcuts, as a pure mapping from a key event to a command so the
// window listener stays small and the rules are testable. Nothing fires while typing in a field.
export type DesignerCommand =
  | { type: "undo" } | { type: "redo" } | { type: "selectAll" } | { type: "group" } | { type: "ungroup" }
  | { type: "duplicate" } | { type: "copy" } | { type: "paste" } | { type: "delete" } | { type: "clear" }
  | { type: "help" } | { type: "nudge"; dx: number; dy: number } | { type: "resize"; dw: number; dh: number };

type KeyLike = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey"> & { target: EventTarget | null };

const ARROWS: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };

export function isTypingTarget(target: EventTarget | null) {
  const element = target as HTMLElement | null;
  return Boolean(element?.closest?.("input, textarea, select, [contenteditable='true'], [role='dialog'], [role='menu']"));
}

export function designerCommand(event: KeyLike): DesignerCommand | null {
  if (isTypingTarget(event.target)) return null;
  const mod = event.ctrlKey || event.metaKey;
  const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
  if (mod && !event.altKey) {
    if (key === "z") return { type: event.shiftKey ? "redo" : "undo" };
    if (key === "y") return { type: "redo" };
    if (key === "a") return { type: "selectAll" };
    if (key === "g") return { type: event.shiftKey ? "ungroup" : "group" };
    if (key === "d") return { type: "duplicate" };
    if (key === "c" && !event.shiftKey) return { type: "copy" };
    if (key === "v" && !event.shiftKey) return { type: "paste" };
    return null;
  }
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

export const SHORTCUT_GROUPS: { title: string; rows: { keys: string[]; action: string }[] }[] = [
  { title: "Select", rows: [
    { keys: ["Click"], action: "Select a layer (a grouped layer selects its group)" },
    { keys: ["Shift", "Click"], action: "Add to or take from the selection (Ctrl or Cmd works too)" },
    { keys: ["Alt", "Click"], action: "Select one layer inside a group" },
    { keys: ["Ctrl or Cmd", "A"], action: "Select every layer on this side" },
    { keys: ["Esc"], action: "Clear the selection" },
  ] },
  { title: "Move and size", rows: [
    { keys: ["Arrows"], action: "Move 1 mm (with Shift, 5 mm)" },
    { keys: ["Alt", "Arrows"], action: "Resize 1 mm (with Shift, 5 mm)" },
    { keys: ["Alt", "Drag"], action: "Move without snapping" },
    { keys: ["Shift", "Drag corner"], action: "Keep the shape (photos, images and logos keep it unless Shift is held)" },
    { keys: ["Shift", "Drag rotate"], action: "Turn in 15° steps" },
  ] },
  { title: "Edit", rows: [
    { keys: ["Ctrl or Cmd", "C"], action: "Copy the selection" },
    { keys: ["Ctrl or Cmd", "V"], action: "Paste, also onto the other side" },
    { keys: ["Ctrl or Cmd", "D"], action: "Duplicate the selection" },
    { keys: ["Ctrl or Cmd", "G"], action: "Group the selection" },
    { keys: ["Shift", "Ctrl or Cmd", "G"], action: "Ungroup" },
    { keys: ["Delete"], action: "Delete the selection (locked layers stay)" },
    { keys: ["Ctrl or Cmd", "Z"], action: "Undo" },
    { keys: ["Shift", "Ctrl or Cmd", "Z"], action: "Redo" },
    { keys: ["?"], action: "Show these shortcuts" },
  ] },
];
