import { describe, expect, it } from "vitest";
import { detailsProblem, emptyDraft, submitBody, todayIso, type JobDraft } from "./jobDraft";
import type { JobType } from "./types";

const NOW = new Date(2026, 4, 10, 12, 0, 0);
const draft = (over: Partial<JobDraft> = {}): JobDraft => ({ ...emptyDraft, title: "Bracket", ...over });
const printer = { queue_id: 3, is_printer: true, consumables: [] } as unknown as JobType;
const laser = { queue_id: 4, is_printer: false, consumables: [] } as unknown as JobType;
const intake = (fields: Record<string, unknown>[]) => ({ intake_schema: { fields } }) as never;

describe("todayIso", () => {
  it("is the local calendar date, not the UTC one", () => expect(todayIso(new Date(2026, 4, 10, 23, 30))).toBe("2026-05-10"));
  it("pads month and day", () => expect(todayIso(new Date(2026, 0, 2, 1, 0))).toBe("2026-01-02"));
});

describe("detailsProblem", () => {
  it("is empty for a complete draft", () => expect(detailsProblem(draft(), printer, undefined, NOW)).toBe(""));
  it("asks for a title", () => expect(detailsProblem(draft({ title: "  " }), printer, undefined, NOW)).toBe("Give your job a title."));
  it.each([0, 1.5, 1000, Number.NaN])("refuses %s copies", (copies) => expect(detailsProblem(draft({ copies }), printer, undefined, NOW)).toBe("Copies must be between 1 and 999."));
  it.each([1, 999])("accepts %i copies", (copies) => expect(detailsProblem(draft({ copies }), printer, undefined, NOW)).toBe(""));
  it("refuses a needed-by date in the past but accepts today and later", () => {
    expect(detailsProblem(draft({ neededBy: "2026-05-09" }), printer, undefined, NOW)).toBe("The needed-by date can't be in the past.");
    expect(detailsProblem(draft({ neededBy: "2026-05-10" }), printer, undefined, NOW)).toBe("");
    expect(detailsProblem(draft({ neededBy: "2026-06-01" }), printer, undefined, NOW)).toBe("");
  });
  it("requires an http(s) source link when one is given", () => {
    expect(detailsProblem(draft({ sourceLink: "ftp://x.org/a" }), printer, undefined, NOW)).toBe("The source link must start with http:// or https://.");
    expect(detailsProblem(draft({ sourceLink: "https://x.org/a b" }), printer, undefined, NOW)).toBe("The source link must start with http:// or https://.");
    expect(detailsProblem(draft({ sourceLink: " HTTPS://x.org/a " }), printer, undefined, NOW)).toBe("");
    expect(detailsProblem(draft({ sourceLink: "   " }), printer, undefined, NOW)).toBe("");
  });
  it("requires non-boolean required intake fields for non-printer types only", () => {
    const schema = intake([{ key: "thickness", label: "Thickness", required: true, type: "number" }, { key: "agree", label: "Agree", required: true, type: "boolean" }, { key: "note", label: "Note", required: false, type: "text" }]);
    expect(detailsProblem(draft(), laser, schema, NOW)).toBe('Fill in "Thickness".');
    expect(detailsProblem(draft({ intake: { thickness: "" } }), laser, schema, NOW)).toBe('Fill in "Thickness".');
    expect(detailsProblem(draft({ intake: { thickness: 0 } }), laser, schema, NOW)).toBe("");
    expect(detailsProblem(draft(), printer, schema, NOW)).toBe("");
    expect(detailsProblem(draft(), laser, undefined, NOW)).toBe("");
  });
  it("asks a printer job with a material and no own material to choose a colour or pool", () => {
    expect(detailsProblem(draft({ material: "PLA" }), printer, undefined, NOW)).toBe("Choose a colour for that material.");
    expect(detailsProblem(draft({ material: "PLA", color: "red" }), printer, undefined, NOW)).toBe("");
    expect(detailsProblem(draft({ material: "PLA", poolId: "4" }), printer, undefined, NOW)).toBe("");
    expect(detailsProblem(draft({ material: "PLA", ownMaterial: true }), printer, undefined, NOW)).toBe("");
    expect(detailsProblem(draft({ material: "PLA" }), laser, undefined, NOW)).toBe("");
  });
  it("reports the first problem when several exist", () => expect(detailsProblem(draft({ title: "", copies: 0 }), printer, undefined, NOW)).toBe("Give your job a title."));
});

describe("submitBody", () => {
  it("builds the shared fields, trimming text and turning blanks into undefined", () => {
    const body = submitBody(printer, draft({ title: " Bracket ", description: "  ", sourceLink: " https://x.org ", copies: 2, neededBy: "", eventId: "7",
      acks: { pickup: true, failure: false, content: true } }), [11, 12], undefined, undefined);
    expect(body).toMatchObject({ queue_id: 3, title: "Bracket", description: undefined, source_link: "https://x.org", file_ids: [11, 12], copies: 2, needed_by: undefined,
      own_material: false, material_note: undefined, event_id: 7, acknowledgements: { pickup_policy: true, failure_policy: false, own_content: true } });
    expect(body).not.toHaveProperty("consumable_estimates");
  });
  it("keeps a material note only when the member brings their own material", () => {
    expect(submitBody(printer, draft({ materialNote: " PETG ", ownMaterial: true }), [], undefined, undefined).material_note).toBe("PETG");
    expect(submitBody(printer, draft({ materialNote: " PETG " }), [], undefined, undefined).material_note).toBeUndefined();
  });
  it("sends a printer job's settings, grams and the chosen pool's material and colour", () => {
    const pools = [{ id: 4, material: "PLA", color: "red" }, { id: 5, material: "PETG", color: "blue" }] as never;
    const body = submitBody(printer, draft({ settings: " 0.2mm ", grams: " 30 ", poolId: "5", material: "x", color: "y" }), [], undefined, pools);
    expect(body).toMatchObject({ preferred_settings: "0.2mm", estimated_filament_grams: "30", material: "PETG", color: "blue", consumable_pool_id: 5 });
  });
  it("falls back to the typed material and colour when no pool is chosen, and to null grams when blank", () => {
    const body = submitBody(printer, draft({ material: " PLA ", color: " red ", grams: "  " }), [], undefined, []);
    expect(body).toMatchObject({ material: "PLA", color: "red", consumable_pool_id: null, estimated_filament_grams: null });
  });
  it("sends no material fields at all for the member's own material", () => {
    const body = submitBody(printer, draft({ ownMaterial: true, poolId: "4", material: "PLA" }), [], undefined, [{ id: 4, material: "PLA", color: "red" }] as never);
    for (const key of ["material", "color", "consumable_pool_id"]) expect(body).not.toHaveProperty(key);
  });
  it("sends the intake payload instead of printer fields for other machine types", () => {
    const body = submitBody(laser, draft({ intake: { thickness: 3 } }), [], intake([{ key: "thickness", label: "T", type: "number" }]), undefined);
    expect(body).toHaveProperty("capability_payload");
    expect(body).not.toHaveProperty("preferred_settings");
  });
});
