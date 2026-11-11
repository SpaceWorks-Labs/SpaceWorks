import { describe, expect, it, vi } from "vitest";

import { doc, layer } from "./designerFixtures.test";
import { issueCount, preflight } from "./preflight";
import { filterHolders, previewValues } from "./previewPerson";
import { designerCommand } from "./shortcuts";
import { runCommand } from "./useDesignerKeys";
import type { DesignerEditing } from "./useDesignerEditing";

const name = (extra = {}) => layer({ id: "name", kind: "data_field", field: "name", text: "{{name}}", colour: "#142C2A",
  x_mm: 5, y_mm: 5, w_mm: 30, h_mm: 6, ...extra });
const qr = (extra = {}) => layer({ id: "qr", kind: "desk_qr", x_mm: 60, y_mm: 20, w_mm: 18, h_mm: 18, ...extra });
const ids = (issues: { id: string }[]) => issues.map((issue) => issue.id.split(":")[0]);

describe("preflight", () => {
  it("passes a clean member card", () => {
    expect(preflight(doc([name(), qr()]), "member_cards")).toEqual([]);
  });

  it("flags text outside the safe area, low contrast and overlapping text", () => {
    const issues = preflight(doc([name({ x_mm: 1 }), layer({ id: "pale", kind: "text", text: "Hi", colour: "#EEEEEE",
      x_mm: 10, y_mm: 6, w_mm: 20, h_mm: 6 }), qr()]), "member_cards");
    expect(ids(issues)).toEqual(expect.arrayContaining(["safe", "contrast", "overlap"]));
    expect(issues[0].severity).toBe("error");
    expect(issues.find((issue) => issue.id.startsWith("contrast"))?.layerId).toBe("pale");
  });

  it("flags QR codes that are too small or turned, and barcodes that are too narrow", () => {
    const issues = preflight(doc([name(), qr({ w_mm: 15, h_mm: 15, rotation: 45 }),
      layer({ id: "bar", kind: "barcode", source: "number", x_mm: 5, y_mm: 40, w_mm: 20, h_mm: 8 })]), "member_cards");
    expect(ids(issues)).toEqual(expect.arrayContaining(["qr-size", "qr-angle", "barcode-size"]));
    const portrait = doc([name(), layer({ id: "bar", kind: "barcode", source: "desk", w_mm: 40, h_mm: 8 })]);
    portrait.front.page_width_mm = 53.98;
    expect(ids(preflight(portrait, "member_cards"))).toContain("barcode-card");
  });

  it("asks for a name, something to scan, and a used back; notes hidden layers", () => {
    const issues = preflight(doc([layer({ id: "h", hidden: true })], [], { back_enabled: true }), "member_cards");
    expect(ids(issues)).toEqual(expect.arrayContaining(["no-name", "no-code", "back-empty", "hidden"]));
    expect(issueCount(issues)).toBe(3);
    expect(ids(preflight(doc([name()]), "event_ticket"))).not.toContain("no-code");
  });
});

describe("preview person", () => {
  const holders = [{ id: 1, kind: "member", name: "Asha Nair", number: "TNK-7", label: "Monthly" },
    { id: 2, kind: "member", name: "Bo Li", number: "TNK-9", label: "Annual" }];
  it("uses the holder's name and number, other fields stay samples", () => {
    const values = previewValues({ kind: "holder", holder: holders[0] });
    expect(values.name).toBe("Asha Nair");
    expect(values.number).toBe("TNK-7");
    expect(values.space).toBe("Tinkerspace");
  });
  it("searches name, number and label in any order", () => {
    expect(filterHolders(holders, "annual li")).toEqual([holders[1]]);
    expect(filterHolders(holders, "tnk-7")).toEqual([holders[0]]);
    expect(filterHolders(holders, "")).toHaveLength(2);
  });
});

describe("shortcuts", () => {
  const key = (key: string, extra: Partial<KeyboardEvent> = {}, target: EventTarget | null = document.body) =>
    designerCommand({ key, ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, target, ...extra });

  it("maps keys to commands", () => {
    expect(key("d", { ctrlKey: true })).toEqual({ type: "duplicate" });
    expect(key("G", { metaKey: true, shiftKey: true })).toEqual({ type: "ungroup" });
    expect(key("g", { ctrlKey: true })).toEqual({ type: "group" });
    expect(key("ArrowLeft", { shiftKey: true })).toEqual({ type: "nudge", dx: -5, dy: 0 });
    expect(key("ArrowDown", { altKey: true })).toEqual({ type: "resize", dw: 0, dh: 1 });
    expect(key("Backspace")).toEqual({ type: "delete" });
    expect(key("Escape")).toEqual({ type: "clear" });
    expect(key("?", { shiftKey: true })).toEqual({ type: "help" });
  });

  it("ignores keys typed into fields and dialogs", () => {
    const input = document.createElement("input");
    document.body.append(input);
    expect(key("Delete", {}, input)).toBeNull();
    expect(key("a", { ctrlKey: true }, input)).toBeNull();
    input.remove();
  });

  it("only nudges on the canvas, and only with a selection and edit rights", () => {
    const editing = { canEdit: true, nudge: vi.fn(), remove: vi.fn(), clear: vi.fn(), canPaste: () => false } as unknown as DesignerEditing;
    const handlers = { editing, selection: ["a"], undo: vi.fn(), redo: vi.fn(), help: vi.fn() };
    expect(runCommand({ type: "nudge", dx: 1, dy: 0 }, handlers, false)).toBe(false);
    expect(runCommand({ type: "nudge", dx: 1, dy: 0 }, handlers, true)).toBe(true);
    expect(editing.nudge).toHaveBeenCalledWith(1, 0);
    expect(runCommand({ type: "delete" }, { ...handlers, selection: [] }, true)).toBe(false);
    expect(runCommand({ type: "paste" }, handlers, true)).toBe(false);
    expect(runCommand({ type: "delete" }, { ...handlers, editing: { ...editing, canEdit: false } }, true)).toBe(false);
  });
});
