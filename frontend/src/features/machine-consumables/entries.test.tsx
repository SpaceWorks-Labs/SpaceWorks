import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { detailsProblem, emptyDraft, submitBody } from "../machine-jobs/jobDraft";
import type { JobType } from "../machine-jobs/types";
import { EntryFields } from "./EntryFields";
import { entriesPayload, entriesProblem, missingRequired, type EntryRow, type EntryValues } from "./entries";

const rows: EntryRow[] = [
  { key: "acrylic", name: "Acrylic", unit: "sheet", attributes: { colour: ["Clear", "Black"] }, required: true },
  { key: "tape", name: "Masking tape", unit: "m", attributes: { size: [] }, required: false },
];
const type = { queue_id: 4, name: "Laser", machine_type_id: 9, machine_type_name: "Laser", machine_type_slug: "laser", is_printer: false, file_groups: [], accepted_extensions: [],
  quotes: "auto", prepay: false, runs_unattended: false, max_open_jobs: null, consumables: rows.map(row => ({ ...row, kind: "material", estimate_by: "member", member_reports: false })) } as JobType;

describe("consumable entries", () => {
  it("requires required rows, whole numbers for sheets and a choice for listed attributes", () => {
    expect(entriesProblem(rows, {})).toMatch(/Acrylic/);
    expect(entriesProblem(rows, { acrylic: { quantity: "1.5", attributes: {} } })).toMatch(/whole numbers/);
    expect(entriesProblem(rows, { acrylic: { quantity: "0", attributes: {} } })).toMatch(/above zero/);
    expect(entriesProblem(rows, { acrylic: { quantity: "-2", attributes: {} } })).toMatch(/above zero/);
    expect(entriesProblem(rows, { acrylic: { quantity: "2", attributes: {} } })).toMatch(/colour/);
    expect(entriesProblem(rows, { acrylic: { quantity: "2", attributes: { colour: "Clear" } }, tape: { quantity: "0.5", attributes: {} } })).toBe("");
    expect(missingRequired(rows, {}).map(row => row.key)).toEqual(["acrylic"]);
  });

  it("builds a payload of filled rows only, with blank attributes dropped", () => {
    const values: EntryValues = { acrylic: { quantity: " 2 ", attributes: { colour: "Clear" } }, tape: { quantity: "", attributes: { size: "" } } };
    expect(entriesPayload(rows, values)).toEqual([{ key: "acrylic", quantity: "2", attributes: { colour: "Clear" } }]);
  });

  it("sends consumable_estimates with the job and blocks the details step until valid", () => {
    const draft = { ...emptyDraft, title: "Sign" };
    expect(detailsProblem(draft, type, undefined)).toMatch(/Acrylic/);
    const ready = { ...draft, consumables: { acrylic: { quantity: "3", attributes: { colour: "Black" } } } };
    expect(detailsProblem(ready, type, undefined)).toBe("");
    expect(submitBody(type, ready, [1], undefined, undefined).consumable_estimates).toEqual([{ key: "acrylic", quantity: "3", attributes: { colour: "Black" } }]);
    expect(submitBody({ ...type, consumables: [] }, draft, [1], undefined, undefined)).not.toHaveProperty("consumable_estimates");
  });

  it("renders units, attribute pickers and the whole-number message", () => {
    function Harness() {
      const [values, setValues] = useState<EntryValues>({});
      return <EntryFields rows={rows} values={values} onChange={setValues} />;
    }
    render(<Harness />);
    expect(screen.getByText("Amount (sheet)")).toBeVisible();
    expect(screen.getByText("Amount (m)")).toBeVisible();
    expect(screen.getByRole("option", { name: "Black" })).toBeInTheDocument();
    expect(screen.getByLabelText("Size")).toHaveAttribute("maxlength", "80");
    fireEvent.change(screen.getAllByRole("spinbutton")[0], { target: { value: "1.5" } });
    expect(screen.getByRole("alert")).toHaveTextContent("Acrylic is counted in whole numbers.");
  });
});
