import type { Technician } from "../technicians/techniciansApi";
import type { IssueDetail, IssueStep } from "./repairsApi";
import type { StepField } from "./StepDialog";
import type { SubjectOption } from "./subjectsApi";

export type StepSpec = { step: IssueStep; title: string; submit: string; fields: StepField[]; note?: string;
  map?: (body: Record<string, unknown>) => Record<string, unknown> };

const PRIORITIES = [{ value: "normal", label: "Normal" }, { value: "high", label: "High" }, { value: "urgent", label: "Urgent" },
  { value: "low", label: "Low" }];
const METHODS = [{ value: "cash", label: "Cash" }, { value: "upi", label: "UPI" }, { value: "bank_transfer", label: "Bank transfer" },
  { value: "cheque", label: "Cheque" }, { value: "other", label: "Other" }];
const nullable = (value: unknown) => (value ? Number(value) : null);

/** The form behind each step; the server re-checks who may take it and in which state. */
export function stepSpecs(issue: IssueDetail, technicians: Technician[], items: SubjectOption[] = []): Record<string, StepSpec> {
  const people = [{ value: "", label: "Not recorded" }, ...technicians.map(row => ({ value: String(row.id), label: row.name }))];
  return {
    triage: { step: "triage", title: "Triage this report", submit: "Triage", fields: [
      { name: "priority", label: "Priority", kind: "select", options: PRIORITIES },
      { name: "note", label: "Note (optional)", kind: "textarea" }],
      note: "With repairs on, triage opens a work order for this subject." },
    reject: { step: "reject", title: "Reject this issue", submit: "Reject", fields: [
      { name: "reason", label: "Why", kind: "textarea", required: true }] },
    visit: { step: "work-log", title: "Log a visit", submit: "Log visit", fields: [
      { name: "occurred_on", label: "Visit date", kind: "date", required: true, initial: new Date().toISOString().slice(0, 10) },
      { name: "contact_id", label: "Who came", kind: "select", options: people },
      { name: "note", label: "What happened", kind: "textarea" },
      { name: "photos", label: "Photos (optional)", kind: "photos" }],
      map: body => ({ ...body, kind: "visit", contact_id: nullable(body.contact_id) }) },
    remark: { step: "work-log", title: "Add a remark", submit: "Add remark", fields: [
      { name: "note", label: "Remark", kind: "textarea" }, { name: "photos", label: "Photos (optional)", kind: "photos" }],
      map: body => ({ ...body, kind: "remark" }) },
    used: { step: "parts", title: "Part used", submit: "Take from stock", fields: [
      items.length
        ? { name: "product_id", label: "Inventory item", kind: "select", required: true, options: items.map(row => ({ value: String(row.id), label: row.label })),
          hint: "Stock goes down through the inventory ledger." }
        : { name: "product_id", label: "Inventory item number", kind: "number", required: true,
          hint: "Ask the inventory team for the item number. Stock goes down through the inventory ledger." },
      { name: "quantity", label: "How many", kind: "number", required: true, initial: "1" }],
      map: body => ({ kind: "used", product_id: Number(body.product_id), quantity: body.quantity }) },
    needed: { step: "parts", title: "Part needed", submit: "Add to To-Buy", fields: [
      { name: "name", label: "Part", kind: "text", required: true },
      { name: "quantity", label: "How many", kind: "number", required: true, initial: "1" }],
      note: "With the area's To-Buy switch on, this becomes a To-Buy row.", map: body => ({ kind: "needed", ...body }) },
    quote: { step: "quote", title: "Record a quote", submit: "Save quote", fields: [
      { name: "amount", label: "Amount", kind: "number", required: true },
      { name: "currency", label: "Currency (3 letters)", kind: "text", required: true, initial: issue.quote_currency || "inr" },
      { name: "contact_id", label: "Quoted by", kind: "select", options: people },
      { name: "note", label: "Note (optional)", kind: "textarea" }],
      map: body => ({ ...body, amount: String(body.amount), contact_id: nullable(body.contact_id) }),
      note: "The area manager or the Space Manager approves it before any payout." },
    payout: { step: "payout", title: "Record the payout", submit: "Record payout", fields: [
      { name: "amount", label: "Amount paid", kind: "number", required: true, initial: issue.quote_amount ?? "" },
      { name: "method", label: "How it was paid", kind: "select", options: METHODS },
      { name: "reference", label: "Reference (optional)", kind: "text" },
      { name: "entry_date", label: "Paid on", kind: "date", initial: new Date().toISOString().slice(0, 10) }],
      map: body => ({ ...body, amount: String(body.amount), currency: issue.quote_currency }),
      note: "Recorded in the finance ledger as a repair expense. Nothing is paid from here." },
    fix: { step: "fix", title: "Mark fixed", submit: "Mark fixed", fields: [
      { name: "resolution", label: "What was fixed", kind: "textarea", required: true },
      { name: "photos", label: "Photos (optional)", kind: "photos" }],
      note: issue.source === "staff" ? undefined : "The person who reported it is told it is fixed." },
    approve: { step: "approve", title: "Approve the quote", submit: "Approve", fields: [{ name: "note", label: "Note (optional)", kind: "textarea" }],
      map: body => ({ ...body, approve: true }), note: `${issue.quote_amount ?? ""} ${issue.quote_currency.toUpperCase()}`.trim() },
    decline: { step: "approve", title: "Decline the quote", submit: "Decline", fields: [{ name: "note", label: "Why (optional)", kind: "textarea" }],
      map: body => ({ ...body, approve: false }) },
    close: { step: "close", title: "Close this issue", submit: "Close", fields: [{ name: "note", label: "Note (optional)", kind: "textarea" }] },
  };
}
