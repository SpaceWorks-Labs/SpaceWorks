import type { ConsumableEntry } from "../../../machine-consumables/entries";
import type { BoardAction, StaffJob } from "./machineJobsApi";

/** Actions that open a form; the rest of `BoardAction` run straight from the card. */
export type DialogAction = Extract<BoardAction, "accept" | "start" | "quote" | "request-changes" | "reject" | "complete" | "fail" | "collect" | "urgent" | "assign">;

export type JobFormValues = {
  machine_id: string; consumable_pool_id: string; estimated_minutes: string; quantity: string; actual_minutes: string;
  percent_complete: string; reason: string; code: string; message: string; fault: string; pickup_location: string;
  pickup_code: string; collector_name: string; note: string; override_length: boolean;
};

export function initialJobValues(job: StaffJob): JobFormValues {
  const estimate = job.estimated_minutes || job.member_estimate_minutes || 60;
  return {
    machine_id: job.preassigned_machine_id ? String(job.preassigned_machine_id) : "", consumable_pool_id: "",
    estimated_minutes: String(estimate), quantity: "", actual_minutes: String(job.estimated_minutes || 0),
    percent_complete: "0", reason: "", code: "", message: "", fault: "", pickup_location: job.pickup_location ?? "",
    pickup_code: "", collector_name: "", note: "", override_length: false,
  };
}

const optional = (value: string) => value.trim() ? value.trim() : undefined;
const number = (value: string) => Number(value || 0);

/** The request body for one job action. Printers keep their gram fields; other types use the generic quantity. */
export function jobActionBody(action: DialogAction, values: JobFormValues, options: { hasPool: boolean; printer: boolean; entries?: ConsumableEntry[] }) {
  const entries = options.entries?.length ? options.entries : undefined;
  const planned = options.hasPool ? optional(values.quantity) : undefined;
  const plannedKey = options.printer ? "planned_grams" : "planned_quantity";
  const actualKey = options.printer ? "actual_grams" : "actual_quantity";
  const pool = options.hasPool && values.consumable_pool_id ? Number(values.consumable_pool_id) : undefined;
  switch (action) {
    case "accept": return { estimated_minutes: number(values.estimated_minutes), ...(options.printer && planned ? { planned_grams: planned } : {}), ...(values.override_length ? { override_length: true } : {}) };
    case "start": return { machine_id: values.machine_id ? Number(values.machine_id) : null, consumable_pool_id: pool, estimated_minutes: number(values.estimated_minutes), [plannedKey]: planned };
    case "quote": return { estimated_minutes: number(values.estimated_minutes), quantity: planned ?? null, consumable_pool_id: pool ?? null, note: values.note.trim(), ...(entries ? { consumable_estimates: entries } : {}) };
    case "request-changes": return { code: values.code, message: values.message.trim() };
    case "reject": return { reason: values.reason.trim(), ...(values.code ? { code: values.code } : {}) };
    case "complete": return { actual_minutes: number(values.actual_minutes), [actualKey]: planned, pickup_location: values.pickup_location.trim(), ...(entries ? { profile_consumptions: entries } : {}) };
    case "fail": return { actual_minutes: number(values.actual_minutes), [actualKey]: planned, percent_complete: number(values.percent_complete), reason: values.reason.trim(), ...(values.code ? { code: values.code } : {}), ...(values.fault ? { fault: values.fault } : {}), ...(entries ? { profile_consumptions: entries } : {}) };
    case "collect": return { pickup_code: values.pickup_code.trim(), collector_name: values.collector_name.trim() };
    case "urgent": return { urgent: true, reason: values.reason.trim() };
    case "assign": return { machine_id: values.machine_id ? Number(values.machine_id) : null };
  }
}

/** Why the confirm button is disabled, or null when the form can be sent. */
export function jobFormBlocker(action: DialogAction, values: JobFormValues): string | null {
  if (action === "request-changes" && (!values.code || !values.message.trim())) return "Choose a reason and write a message.";
  if ((action === "reject" || action === "fail" || action === "urgent") && !values.reason.trim()) return "Add a reason.";
  if (action === "start" && !values.machine_id) return "Choose a machine.";
  if ((action === "accept" || action === "start" || action === "quote") && !(Number(values.estimated_minutes) >= 0 && values.estimated_minutes !== "")) return "Enter the estimated minutes.";
  return null;
}
