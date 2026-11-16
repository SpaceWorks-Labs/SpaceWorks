import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { FormBuilderV2 } from "./FormBuilderV2";
import { FormV2Fields } from "./FormV2Fields";
import { formItems, withoutQuestion } from "./sections";
import { visibleQuestions } from "./conditions";
import type { FormSchemaV2, FormState } from "./types";

// Parity O-B2 / O-F2: section headings render by the schema_items rule -- a heading shows only when a
// visible question follows it before the next heading.
const schema: FormSchemaV2 = {
  schema_version: 2, form_id: "join", revision: 1,
  questions: [
    { id: "name", type: "short_text", label: "Your name", required: true },
    { id: "student", type: "yes_no", label: "Are you a student?" },
    { id: "college", type: "short_text", label: "College", show_if: { field_id: "student", op: "eq", value: true } },
    { id: "skills", type: "long_text", label: "Skills" },
  ],
  sections: [
    { id: "about", before: "name", heading: "About you", help: "Tell us who you are." },
    { id: "study", before: "college", heading: "Your studies" },
    { id: "work", before: "skills", heading: "Your work" },
  ],
};
const state = (answers: Record<string, unknown> = {}): FormState => ({ answers, derivations: {}, save_choices: {}, saved_detail_versions: {} });

describe("form section headings", () => {
  it("drops a heading whose questions are all hidden, and keeps the rest in order", () => {
    const hidden = formItems(schema, visibleQuestions(schema, {}));
    expect(hidden.map((item) => item.kind === "section" ? `#${item.section.id}` : item.question.id))
      .toEqual(["#about", "name", "student", "#work", "skills"]);
    const shown = formItems(schema, visibleQuestions(schema, { student: true }));
    expect(shown.filter((item) => item.kind === "section").map((item) => item.kind === "section" && item.section.id)).toEqual(["about", "study", "work"]);
  });

  it("moves a heading down to the first visible question when its own question is hidden", () => {
    const moved: FormSchemaV2 = { ...schema, sections: [{ id: "study", before: "college", heading: "Your studies" }] };
    const items = formItems(moved, visibleQuestions(moved, {}));
    // "college" is hidden, so "Your studies" introduces the next visible question instead.
    expect(items.map((item) => item.kind === "section" ? `#${item.section.id}` : item.question.id)).toEqual(["name", "student", "#study", "skills"]);
  });

  it("renders headings and help text as headings, never as questions", () => {
    render(<FormV2Fields schema={schema} value={state()} onChange={() => undefined} />);
    expect(screen.getByRole("heading", { name: "About you" })).toBeVisible();
    expect(screen.getByText("Tell us who you are.")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Your studies" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Your work" })).toBeVisible();
    expect(screen.queryByRole("group", { name: /About you/ })).toBeNull();
  });

  it("re-anchors a heading when its question is deleted, and drops it with the last question", () => {
    expect(withoutQuestion(schema, "name").sections?.find((section) => section.id === "about")?.before).toBe("student");
    const single: FormSchemaV2 = { ...schema, questions: [schema.questions[0]], sections: [{ id: "about", before: "name", heading: "About you" }] };
    expect(withoutQuestion(single, "name").sections).toEqual([]);
  });
});

function Builder({ initial, memberCard = false }: { initial: FormSchemaV2; memberCard?: boolean }) {
  const [value, setValue] = useState(initial);
  return <><FormBuilderV2 value={value} onChange={setValue} memberCard={memberCard} /><output data-testid="schema">{JSON.stringify(value)}</output></>;
}
const saved = () => JSON.parse(screen.getByTestId("schema").textContent ?? "{}") as FormSchemaV2;

describe("form builder section items", () => {
  it("adds a heading above the first question without one and lets the author move it", () => {
    render(<Builder initial={{ ...schema, sections: [] }} />);
    fireEvent.click(screen.getByRole("button", { name: "Add section heading" }));
    const editor = screen.getByRole("group", { name: "Section heading: New section" });
    fireEvent.change(within(editor).getByLabelText("Heading"), { target: { value: "Contact" } });
    fireEvent.change(within(editor).getByLabelText("Shown above"), { target: { value: "skills" } });
    expect(saved().sections).toEqual([expect.objectContaining({ before: "skills", heading: "Contact" })]);
    fireEvent.click(screen.getByRole("button", { name: "Remove heading Contact" }));
    expect(saved().sections).toEqual([]);
  });

  it("cannot add a heading to a form with no questions", () => {
    render(<Builder initial={{ schema_version: 2, form_id: "f", revision: 1, questions: [] }} />);
    expect(screen.getByRole("button", { name: "Add section heading" })).toBeDisabled();
  });

  it("offers the member-card print toggle only on membership forms, and never for sensitive answers", () => {
    const { unmount } = render(<Builder initial={{ ...schema, sections: [] }} />);
    expect(screen.queryAllByLabelText("Can print on the member card")).toHaveLength(0);
    unmount();
    render(<Builder initial={{ ...schema, sections: [] }} memberCard />);
    const boxes = screen.getAllByLabelText("Can print on the member card");
    fireEvent.click(boxes[0]);
    expect(saved().questions[0].printable).toBe(true);
    fireEvent.click(screen.getAllByLabelText("Sensitive answer")[0]);
    expect(saved().questions[0].printable).toBeUndefined();
    expect(screen.getAllByLabelText("Can print on the member card")[0]).toBeDisabled();
  });
});
