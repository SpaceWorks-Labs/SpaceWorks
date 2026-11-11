import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FormV2Fields } from "./FormV2Fields";
import { FormBuilderV2 } from "./FormBuilderV2";
import { QuestionEditor } from "./QuestionEditor";
import { CustomAnswersView } from "./CustomAnswersView";
import { CustomFormFields } from "./CustomFormFields";
import { MoneyInput } from "./MoneyInput";
import { FileInput } from "./FileInput";
import { ItineraryInput } from "./ItineraryInput";
import { ConditionEditor } from "./ConditionEditor";
import { memberFormInput } from "./conditions";
import { upgradeLegacyForm } from "./upgradeLegacyForm";
import { expectNoA11yViolations } from "../../test/axe";
import type { FileReference, FormSchemaV2, FormState, Question } from "./types";

const file: Question = { id: "receipt", type: "file", label: "Documents", required: true,
  file: { purpose: "stage_form_file", max_files: 2, max_bytes_each: 100 } };
const money: Question = { id: "estimate", type: "money", label: "Estimate",
  money: { currencies: ["INR", "JPY", "KWD"], min_minor: 0, max_minor: 100000 } };
const journey: Question = { id: "trip", type: "itinerary", label: "Journey", itinerary: { modes: ["rail", "air"] } };
const reference: FileReference = { asset_id: 91, generation: 1, sha256: "a".repeat(64) };
const schema = (...questions: Question[]): FormSchemaV2 => ({ schema_version: 2, form_id: "travel", revision: 1, questions });
const empty = (): FormState => ({ answers: {}, derivations: {}, save_choices: {}, saved_detail_versions: {} });

describe("reimbursement compound fields", () => {
  it("takes a decimal amount and emits exact integer minor units in the chosen currency", () => {
    const change = vi.fn();
    function Harness() {
      const [value, setValue] = useState<unknown>(undefined);
      return <MoneyInput question={money} value={value} onChange={next => { change(next); setValue(next); }} />;
    }
    render(<Harness />);
    fireEvent.change(screen.getByLabelText("Estimate amount"), { target: { value: "1250.50" } });
    expect(change).toHaveBeenLastCalledWith({ amount_minor: 125050, currency: "INR" });
    fireEvent.change(screen.getByLabelText("Estimate currency"), { target: { value: "KWD" } });
    expect(change).toHaveBeenLastCalledWith({ amount_minor: 1250500, currency: "KWD" });
    fireEvent.change(screen.getByLabelText("Estimate currency"), { target: { value: "JPY" } });
    expect(change).toHaveBeenLastCalledWith({ amount_minor: "1250.50", currency: "JPY" });
    fireEvent.change(screen.getByLabelText("Estimate amount"), { target: { value: "1e2" } });
    expect(change).toHaveBeenLastCalledWith({ amount_minor: "1e2", currency: "JPY" });
  });

  it("shows a stored minor amount back as a decimal", () => {
    render(<MoneyInput question={money} value={{ amount_minor: 125000, currency: "INR" }} onChange={vi.fn()} />);
    expect(screen.getByLabelText("Estimate amount")).toHaveValue("1250.00");
  });

  it("connects compound errors to labelled keyboard controls", () => {
    render(<FormV2Fields schema={schema(money, journey)} value={empty()} onChange={vi.fn()}
      errors={{ estimate: { amount_minor: ["Too large"] }, trip: { arrive_at: ["Arrival before departure"] } }} />);
    expect(screen.getByLabelText("Estimate amount")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Estimate currency")).toHaveAccessibleDescription(expect.stringContaining("Too large"));
    expect(screen.getByLabelText("Origin")).toHaveAccessibleDescription(expect.stringContaining("Arrival before departure"));
  });

  it("keeps timezone-aware instants and explicit null unknown itinerary fields", () => {
    const change = vi.fn();
    const view = render(<ItineraryInput question={journey} value={{ mode: "rail" }} onChange={change} />);
    fireEvent.change(screen.getByLabelText(/^Departure/), { target: { value: "2026-12-01T12:00" } });
    expect(change.mock.lastCall?.[0].depart_at).toMatch(/^2026-12-01T.*Z$/);
    fireEvent.change(screen.getByLabelText("Origin"), { target: { value: "Kochi" } });
    expect(change).toHaveBeenLastCalledWith({ mode: "rail", origin: "Kochi" });
    view.rerender(<ItineraryInput question={journey} value={{ mode: "rail", origin: "Kochi" }} onChange={change} />);
    fireEvent.change(screen.getByLabelText("Origin"), { target: { value: "" } });
    expect(change).toHaveBeenLastCalledWith({ mode: "rail", origin: null });
  });

  it("binds uploads through the injected authorized adapter and supports removal", async () => {
    const upload = vi.fn().mockResolvedValue([reference]);
    const change = vi.fn();
    const view = render(<FileInput question={file} value={[]} onChange={change} upload={upload} />);
    const selected = new File(["receipt"], "receipt.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("Documents files"), { target: { files: [selected] } });
    await waitFor(() => expect(change).toHaveBeenCalledWith([reference]));
    expect(upload).toHaveBeenCalledWith(file, [selected]);
    view.rerender(<FileInput question={file} value={[reference]} onChange={change} upload={upload} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove file 1" }));
    expect(change).toHaveBeenLastCalledWith([]);
  });

  it("rejects oversized files locally and leaves failed uploads retryable without provider error leakage", async () => {
    const upload = vi.fn().mockRejectedValueOnce(new Error("private provider payload")).mockResolvedValue([reference]);
    const change = vi.fn();
    render(<FileInput question={file} value={[]} onChange={change} upload={upload} />);
    const input = screen.getByLabelText("Documents files");
    fireEvent.change(input, { target: { files: [new File(["a".repeat(101)], "big.pdf")] } });
    expect(upload).not.toHaveBeenCalled();
    const selected = new File(["receipt"], "receipt.pdf");
    fireEvent.change(input, { target: { files: [selected] } });
    await screen.findByText(/Couldn’t upload/);
    expect(screen.queryByText(/private provider/)).not.toBeInTheDocument();
    fireEvent.change(input, { target: { files: [selected] } });
    await waitFor(() => expect(change).toHaveBeenCalledWith([reference]));
  });

  it("does not publish late upload results after the form is unmounted", async () => {
    let resolve!: (value: FileReference[]) => void;
    const upload = vi.fn(() => new Promise<FileReference[]>(done => { resolve = done; }));
    const change = vi.fn();
    const view = render(<FileInput question={file} value={[]} onChange={change} upload={upload} />);
    fireEvent.change(screen.getByLabelText("Documents files"), { target: { files: [new File(["a"], "a.pdf")] } });
    view.unmount(); resolve([reference]);
    await waitFor(() => expect(upload).toHaveBeenCalledOnce());
    expect(change).not.toHaveBeenCalled();
  });

  it("does not enable a finance-purpose upload from stage or generic context", () => {
    const finance = { ...file, file: { ...file.file!, purpose: "reimbursement_receipt" as const }, sensitive: true };
    const view = render(<FormV2Fields schema={schema(finance)} value={empty()} onChange={vi.fn()} context="stage" uploadFiles={vi.fn()} />);
    expect(screen.getByLabelText("Documents files")).toBeDisabled();
    view.rerender(<FormV2Fields schema={schema(file)} value={empty()} onChange={vi.fn()} uploadFiles={vi.fn()} />);
    expect(screen.getByLabelText("Documents files")).toBeDisabled();
  });

  it("keeps map/form/date spelling, prunes hidden files and never silently saves sensitive values", () => {
    const form = { ...schema({ id: "show", type: "yes_no", label: "Travel?" },
      { ...file, show_if: { field_id: "show", op: "eq", value: true } },
      { id: "name", type: "short_text", label: "Name", sensitive: true, profile_field_key: "name" }),
      event_context: { event_id: 1, event_date_revision: 2, timezone_name: "UTC", as_of_date: "2026-12-01" } };
    const input = memberFormInput(form, { ...empty(), answers: { show: false, receipt: [reference], name: "Member" } });
    expect(input).toEqual({ form: { schema_version: 2, form_id: "travel", revision: 1 }, answers: { show: false, name: "Member" },
      derivations: {}, save_choices: { name: false }, saved_detail_versions: {}, event_date_revision: 2 });
    const opted = memberFormInput(form, { ...empty(), answers: { name: "Member" }, save_choices: { name: true }, saved_detail_versions: { name: 4 } });
    expect(opted.saved_detail_versions).toEqual({ name: 4 });
  });

  it("renders sensitive save consent off by default and explicit disclosure copy", () => {
    function Form() {
      const [state, setState] = useState(empty());
      return <FormV2Fields schema={schema({ id: "name", type: "short_text", label: "Name", sensitive: true, profile_field_key: "name" })} value={state} onChange={setState} />;
    }
    render(<Form />);
    expect(screen.getByText("Only you and finance can see this answer.")).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    fireEvent.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("hides stage DOB/age types and mappings and generic file types", () => {
    const view = render(<FormBuilderV2 value={schema()} onChange={vi.fn()} context="stage" />);
    expect(screen.queryByRole("option", { name: "Date of birth" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Age at the event" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "File upload" })).toBeInTheDocument();
    view.rerender(<FormBuilderV2 value={schema()} onChange={vi.fn()} />);
    expect(screen.queryByRole("option", { name: "File upload" })).not.toBeInTheDocument();
    view.rerender(<QuestionEditor question={{ id: "q", type: "date", label: "Date" }} earlier={[]} onChange={vi.fn()} context="stage" />);
    expect(screen.queryByRole("option", { name: "date_of_birth" })).not.toBeInTheDocument();
  });

  it("authors configured compound questions and sensitive finance files", () => {
    const change = vi.fn();
    render(<FormBuilderV2 value={schema()} onChange={change} context="claim" />);
    fireEvent.change(screen.getByLabelText("Question type"), { target: { value: "file" } });
    fireEvent.click(screen.getByRole("button", { name: "Add question" }));
    expect(change.mock.lastCall?.[0].questions[0]).toMatchObject({ type: "file", sensitive: true,
      file: { purpose: "reimbursement_receipt" }, disclosure: { organizer: false, reviewer: false, judge: false } });
  });

  it("keeps sensitive questions out of condition authoring", () => {
    render(<ConditionEditor earlier={[{ id: "private", type: "yes_no", label: "Private", sensitive: true }]} onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Add condition" })).toBeDisabled();
  });

  it("displays compound projections without exposing asset IDs and hides raw sensitive rows by default", () => {
    const snapshot = { version: 2 as const, form_id: "travel", form_revision: 1, answers: [
      { id: "m", type: "money" as const, label: "Estimate", value: { amount_minor: 125000, currency: "INR" } },
      { id: "f", type: "file" as const, label: "Receipt", value: [reference] },
      { id: "s", type: "itinerary" as const, label: "Journey", sensitive: true, value: { mode: "rail", origin: "Private origin" } }] };
    const view = render(<CustomAnswersView snapshot={snapshot} />);
    expect(screen.getByText("₹1,250.00")).toBeInTheDocument();
    expect(screen.getByText("1 file attached")).toBeInTheDocument();
    expect(screen.queryByText(/Private origin/)).not.toBeInTheDocument();
    expect(screen.queryByText(reference.sha256)).not.toBeInTheDocument();
    view.rerender(<CustomAnswersView snapshot={snapshot} viewer="owner" />);
    expect(screen.getByText("rail · Private origin")).toBeInTheDocument();
  });

  it("preserves legacy list rendering and explicit upgrade semantics", () => {
    const legacy = [{ id: "yes", type: "yes_no" as const, label: "Joining", required: true, options: [] }];
    render(<CustomFormFields schema={legacy} answers={{ yes: false }} onChange={vi.fn()} />);
    expect(screen.getByRole("radio", { name: "No" })).toBeChecked();
    expect(upgradeLegacyForm(legacy, "registration").questions[0]).toMatchObject({ id: "yes", type: "yes_no", required: true });
  });

  it("meets the accessibility floor for compound controls and linked errors", async () => {
    const view = render(<FormV2Fields schema={schema(money, journey, file)} value={empty()} onChange={vi.fn()}
      context="stage" uploadFiles={vi.fn()} errors={{ estimate: { amount_minor: ["Too large"] } }} />);
    await expectNoA11yViolations(view.container);
  });
});
