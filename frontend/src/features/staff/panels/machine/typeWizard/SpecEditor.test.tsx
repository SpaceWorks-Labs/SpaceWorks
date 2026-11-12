import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TemplateForm } from "./TemplateForm";
import { baseSpec, renderWithQuery } from "./test/stepTestKit";
import { validateSpec } from "./specValidate";
import type { TypeTemplate } from "./templatesApi";

const source = { id: null, key: "laser_cutter", name: "Laser cutter", description: "Cuts sheets", category: "Fabrication", icon: "zap", spec: baseSpec, is_builtin: true, customised: false, based_on: null, is_active: true } as unknown as TypeTemplate;
const show = (props: { error?: string; onSave?: (body: unknown) => void } = {}) => renderWithQuery(
  <TemplateForm source={source} copy={false} saving={false} error={props.error} onSave={props.onSave ?? (() => undefined)} onCancel={() => undefined} />);
const section = (name: string) => screen.getByText(name, { selector: "summary" }).closest("details") as HTMLElement;

describe("template spec editor", () => {
  it("edits a consumable and a maintenance item and saves the new spec", () => {
    const onSave = vi.fn();
    show({ onSave });
    fireEvent.click(screen.getByRole("button", { name: "Edit consumable Acrylic sheet" }));
    fireEvent.change(within(section("Consumables")).getByLabelText("Name"), { target: { value: "Acrylic sheet 3mm" } });
    expect(screen.queryByLabelText(/Price per unit/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Add consumable" }));
    fireEvent.change(screen.getByLabelText("Interval for maintenance item 1"), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Save template" }));
    const body = onSave.mock.calls[0][0];
    expect(body.spec.consumables[0]).toEqual({ key: "acrylic_sheet", name: "Acrylic sheet 3mm", kind: "material", unit: "sheet", required: true, estimate_by: "member", record_by: ["staff"], attributes: {} });
    expect(body.spec.maintenance).toEqual([{ title: "Clean the lens", trigger: "days", interval: 30 }]);
  });

  it("refuses a bad key and a bad interval before saving, in their own sections", () => {
    const onSave = vi.fn();
    show({ onSave });
    fireEvent.click(screen.getByRole("button", { name: "Edit consumable Acrylic sheet" }));
    fireEvent.change(within(section("Consumables")).getByLabelText("Key"), { target: { value: "Bad-Key" } });
    expect(screen.getByRole("button", { name: "Add consumable" })).toBeDisabled();
    fireEvent.change(within(section("Consumables")).getByLabelText("Key"), { target: { value: "sheet_id" } });
    expect(screen.getByRole("button", { name: "Add consumable" })).toBeDisabled();
    fireEvent.click(within(section("Consumables")).getByRole("button", { name: "Cancel" }));
    fireEvent.change(screen.getByLabelText("Interval for maintenance item 1"), { target: { value: "0" } });
    expect(within(section("Maintenance")).getByRole("alert")).toHaveTextContent("1 to 100000");
    expect(screen.getByRole("button", { name: "Save template" })).toBeDisabled();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("flags duplicate and over-long lists the way the server does", () => {
    const rows = Array.from({ length: 31 }, (_, index) => ({ key: `item_${index}`, name: "x" }));
    expect(validateSpec({ ...baseSpec, consumables: rows } as never).consumables).toMatch(/at most 30/);
    expect(validateSpec({ ...baseSpec, consumables: [{ key: "a", name: "A" }, { key: "a", name: "B" }] } as never).consumables).toMatch(/Two consumable/);
    expect(validateSpec({ ...baseSpec, intake_fields: [{ key: "ok", label: "Ok", type: "text" }, { key: "1x", label: "Bad", type: "text" }] } as never).intake_fields).toMatch(/starts with a letter/);
    expect(validateSpec(baseSpec as never)).toEqual({});
  });

  it("shows a server refusal under the section it names", () => {
    show({ error: "spec.maintenance.0.interval: Ensure this value is less than or equal to 100000." });
    expect(within(section("Maintenance")).getByRole("alert")).toHaveTextContent("spec.maintenance.0.interval");
    expect(within(section("Consumables")).queryByRole("alert")).toBeNull();
  });
});
