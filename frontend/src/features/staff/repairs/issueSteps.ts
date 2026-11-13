import { t } from "@lingui/core/macro";
import type { Technician } from "../technicians/techniciansApi";
import type { IssueDetail, IssueStep } from "./repairsApi";
import type { StepField } from "./StepDialog";
import type { SubjectOption } from "./subjectsApi";

export type StepSpec = { step: IssueStep; title: string; submit: string; fields: StepField[]; note?: string;
  map?: (body: Record<string, unknown>) => Record<string, unknown> };

const PRIORITIES = [{ value: "normal", label: t`Normal` }, { value: "high", label: t`High` }, { value: "urgent", label: t`Urgent` },
  { value: "low", label: t`Low` }];
const METHODS = [{ value: "cash", label: t`Cash` }, { value: "upi", label: "UPI" }, { value: "bank_transfer", label: t`Bank transfer` },
  { value: "cheque", label: t`Cheque` }, { value: "other", label: t`Other` }];
const nullable = (value: unknown) => (value ? Number(value) : null);

/** The form behind each step; the server re-checks who may take it and in which state. */
export function stepSpecs(issue: IssueDetail, technicians: Technician[], items: SubjectOption[] = []): Record<string, StepSpec> {
  const people = [{ value: "", label: t`Not recorded` }, ...technicians.map(row => ({ value: String(row.id), label: row.name }))];
  return {
    triage: { step: "triage", title: t`Triage this report`, submit: "Triage", fields: [
      { name: "priority", label: t`Priority`, kind: "select", options: PRIORITIES },
      { name: "note", label: t`Note (optional)`, kind: "textarea" }],
      note: t`With repairs on, triage opens a work order for this subject.` },
    reject: { step: "reject", title: t`Reject this issue`, submit: "Reject", fields: [
      { name: "reason", label: t`Why`, kind: "textarea", required: true }] },
    visit: { step: "work-log", title: t`Log a visit`, submit: "Log visit", fields: [
      { name: "occurred_on", label: t`Visit date`, kind: "date", required: true, initial: new Date().toISOString().slice(0, 10) },
      { name: "contact_id", label: t`Who came`, kind: "select", options: people },
      { name: "note", label: t`What happened`, kind: "textarea" },
      { name: "photos", label: t`Photos (optional)`, kind: "photos" }],
      map: body => ({ ...body, kind: "visit", contact_id: nullable(body.contact_id) }) },
    remark: { step: "work-log", title: t`Add a remark`, submit: "Add remark", fields: [
      { name: "note", label: t`Remark`, kind: "textarea" }, { name: "photos", label: t`Photos (optional)`, kind: "photos" }],
      map: body => ({ ...body, kind: "remark" }) },
    used: { step: "parts", title: t`Part used`, submit: "Take from stock", fields: [
      items.length
        ? { name: "product_id", label: t`Inventory item`, kind: "select", required: true, options: items.map(row => ({ value: String(row.id), label: row.label })),
          hint: t`Stock goes down through the inventory ledger.` }
        : { name: "product_id", label: t`Inventory item number`, kind: "number", required: true,
          hint: t`Ask the inventory team for the item number. Stock goes down through the inventory ledger.` },
      { name: "quantity", label: t`How many`, kind: "number", required: true, initial: "1" }],
      map: body => ({ kind: "used", product_id: Number(body.product_id), quantity: body.quantity }) },
    needed: { step: "parts", title: t`Part needed`, submit: "Add to To-Buy", fields: [
      { name: "name", label: t`Part`, kind: "text", required: true },
      { name: "quantity", label: t`How many`, kind: "number", required: true, initial: "1" }],
      note: t`With the area's To-Buy switch on, this becomes a To-Buy row.`, map: body => ({ kind: "needed", ...body }) },
    quote: { step: "quote", title: t`Record a quote`, submit: "Save quote", fields: [
      { name: "amount", label: t`Amount`, kind: "number", required: true },
      { name: "currency", label: t`Currency (3 letters)`, kind: "text", required: true, initial: issue.quote_currency || "inr" },
      { name: "contact_id", label: t`Quoted by`, kind: "select", options: people },
      { name: "note", label: t`Note (optional)`, kind: "textarea" }],
      map: body => ({ ...body, amount: String(body.amount), contact_id: nullable(body.contact_id) }),
      note: t`The area manager or the Space Manager approves it before any payout.` },
    payout: { step: "payout", title: t`Record the payout`, submit: "Record payout", fields: [
      { name: "amount", label: t`Amount paid`, kind: "number", required: true, initial: issue.quote_amount ?? "" },
      { name: "method", label: t`How it was paid`, kind: "select", options: METHODS },
      { name: "reference", label: t`Reference (optional)`, kind: "text" },
      { name: "entry_date", label: t`Paid on`, kind: "date", initial: new Date().toISOString().slice(0, 10) }],
      map: body => ({ ...body, amount: String(body.amount), currency: issue.quote_currency }),
      note: t`Recorded in the finance ledger as a repair expense. Nothing is paid from here.` },
    fix: { step: "fix", title: t`Mark fixed`, submit: "Mark fixed", fields: [
      { name: "resolution", label: t`What was fixed`, kind: "textarea", required: true },
      { name: "photos", label: t`Photos (optional)`, kind: "photos" }],
      note: issue.source === "staff" ? undefined : t`The person who reported it is told it is fixed.` },
    approve: { step: "approve", title: t`Approve the quote`, submit: "Approve", fields: [{ name: "note", label: t`Note (optional)`, kind: "textarea" }],
      map: body => ({ ...body, approve: true }), note: `${issue.quote_amount ?? ""} ${issue.quote_currency.toUpperCase()}`.trim() },
    decline: { step: "approve", title: t`Decline the quote`, submit: "Decline", fields: [{ name: "note", label: t`Why (optional)`, kind: "textarea" }],
      map: body => ({ ...body, approve: false }) },
    close: { step: "close", title: t`Close this issue`, submit: "Close", fields: [{ name: "note", label: t`Note (optional)`, kind: "textarea" }] },
  };
}
