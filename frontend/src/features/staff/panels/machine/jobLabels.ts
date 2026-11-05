/** Reason-code wording for the uniform job flow (#141/#142). Codes mirror the backend choices. */
export const CHANGE_CODES: [string, string][] = [
  ["file_problem", "Problem with the file"], ["wrong_format", "Wrong file format"], ["too_large", "Too large for the machine"],
  ["split_needed", "Needs splitting into parts"], ["material_mismatch", "Material does not suit the job"],
  ["missing_details", "Missing details"], ["other", "Something else"],
];

export const REJECT_CODES: [string, string][] = [
  ["not_allowed_content", "Content not allowed here"], ["ip_concern", "Copyright or IP concern"],
  ["not_eligible", "Member not eligible"], ["for_someone_else", "Made for someone else"],
  ["better_made_another_way", "Better made another way"], ["too_large", "Too large for the machine"], ["other", "Something else"],
];

export const FAIL_CODES: [string, string][] = [
  ["adhesion", "Bed adhesion"], ["nozzle_jam", "Nozzle jam"], ["material_ran_out", "Material ran out"],
  ["machine_fault", "Machine fault"], ["power_cut", "Power cut"], ["operator_error", "Operator error"],
  ["file_problem", "Problem with the file"], ["material_defect", "Material defect"], ["other", "Something else"],
];

export const FILE_GROUPS: [string, string][] = [
  ["fab-2d", "2D cutting and engraving"], ["fab-3dprint", "3D printing"], ["fab-cnc", "CNC milling"],
  ["hardware-cad", "Mechanical CAD"], ["hardware-pcb", "Circuit boards"], ["embroidery", "Embroidery"],
];

/** #142 OQ-6: the at-risk flag's wording per reason (the needed-by date never reorders the queue). */
export const AT_RISK_LABELS: Record<string, string> = {
  needed_by_passed: "Past its needed-by date",
  eta_after_needed_by: "At risk: finishes after its needed-by date",
  needed_by_soon: "At risk: needed by tomorrow, no estimate yet",
};

/** Staff-facing explanation for a refused job action, keyed by the API error code. */
export const ACTION_ERROR_HELP: Record<string, string> = {
  quote_required: "This machine type needs a quote the member approves first. Send a quote instead.",
  job_too_long: "This job is longer than this machine type allows. Tick “Accept anyway” to override.",
  payment_due: "This job’s charge must be paid before pickup. Settle it in Payments, then collect.",
  machine_locked_out: "This machine is locked out until its overdue maintenance is done.",
  machine_booked: "Someone else holds a booking on this machine right now. Choose another machine or wait.",
};
