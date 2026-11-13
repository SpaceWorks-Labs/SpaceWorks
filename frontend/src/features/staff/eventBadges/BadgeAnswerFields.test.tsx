import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";

import { BadgeAnswerFields } from "./BadgeAnswerFields";
import { defaultSettings, normalizeSettings, type BadgeSettings } from "./badgeNormalize";

const FIELDS = [{ key: "registration:company", label: "Company" }, { key: "registration:diet", label: "Dietary needs" },
  { key: "attendee:team", label: "Team" }];

function Harness({ initial, max = 8, onChange }: { initial: Partial<BadgeSettings>; max?: number; onChange?: (s: BadgeSettings) => void }) {
  const [settings, setSettings] = useState<BadgeSettings>({ ...defaultSettings("Night", "Space"), ...initial });
  return <BadgeAnswerFields settings={settings} fields={FIELDS} max={max} update={(patch) => {
    const next = { ...normalizeSettings({ ...settings, ...patch }), ...(patch.printFieldLabels ? { printFieldLabels: patch.printFieldLabels } : {}) };
    setSettings(next); onChange?.(next);
  }} />;
}

it("adds an answer with its form label, reorders and relabels it", () => {
  let latest: BadgeSettings | null = null;
  render(<Harness initial={{}} onChange={(s) => { latest = s; }} />);
  fireEvent.click(screen.getByRole("button", { name: "Add Company" }));
  fireEvent.click(screen.getByRole("button", { name: "Add Dietary needs" }));
  expect(latest!.printFieldKeys).toEqual(["registration:company", "registration:diet"]);
  expect(latest!.printFieldLabels["registration:company"]).toBe("Company");
  fireEvent.click(screen.getByRole("button", { name: "Move Dietary needs up" }));
  expect(latest!.printFieldKeys).toEqual(["registration:diet", "registration:company"]);
  fireEvent.change(screen.getByRole("textbox", { name: "Printed label for Company" }), { target: { value: "Works at" } });
  expect(latest!.printFieldLabels["registration:company"]).toBe("Works at");
  fireEvent.click(screen.getByRole("button", { name: "Remove Company" }));
  expect(latest!.printFieldKeys).toEqual(["registration:diet"]);
});

it("matches a bare imported key to the form and offers to remove keys the form doesn't have", () => {
  let latest: BadgeSettings | null = null;
  render(<Harness initial={{ printFieldKeys: ["company", "shoe_size"] }} onChange={(s) => { latest = s; }} />);
  expect(screen.getAllByText("Not on this event's form")).toHaveLength(1);
  expect(screen.queryByRole("button", { name: "Add Company" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Remove the unmatched answers" }));
  expect(latest!.printFieldKeys).toEqual(["company"]);
});

it("stops adding at the print limit", () => {
  render(<Harness initial={{ printFieldKeys: ["registration:company"] }} max={1} />);
  expect(screen.getByRole("button", { name: "Add Dietary needs" })).toBeDisabled();
  expect(screen.getByText("A badge prints at most 1 answers.")).toBeInTheDocument();
});
