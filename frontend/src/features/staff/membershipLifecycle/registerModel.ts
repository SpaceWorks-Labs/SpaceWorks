import { t } from "@lingui/core/macro";

// Parity O-B2: the member register's filters, in the shared member-filter contract the server applies
// identically to the register, the roster and the card-job resolver (`admin_api/member_register_filters.py`).

export const REGISTER_FILTER_DEFAULTS = {
  q: "", chip: "", plan: "", title: "", unit: "", role: "", joined_after: "", joined_before: "",
  staff: "", verified: "", minor: "", volunteer: "", waiver_needed: "",
};
export type RegisterFilterValues = typeof REGISTER_FILTER_DEFAULTS;
export type RegisterChip = "active" | "expiring" | "grace" | "lapsed" | "upcoming" | "no_term" | "approval" | "payment" | "changes";

/** The chips in reading order: term standings first, then the steps an applicant is waiting on. */
export function registerChips(askChanges: boolean): { key: RegisterChip; label: string }[] {
  return [
    { key: "active", label: t`Active` }, { key: "expiring", label: t`Ending in 30 days` }, { key: "grace", label: t`In grace` },
    { key: "lapsed", label: t`Lapsed` }, { key: "upcoming", label: t`Upcoming` }, { key: "no_term", label: t`No term` },
    { key: "approval", label: t`Awaiting approval` }, { key: "payment", label: t`Awaiting payment` },
    ...(askChanges ? [{ key: "changes" as const, label: t`Changes requested` }] : []),
  ];
}

/** The register's historical `?standing=` deep links (term standings) read as chips. */
export function chipFromStanding(standing: string): string {
  if (standing === "ending_soon") return "expiring";
  return ["active", "grace", "lapsed", "upcoming", "no_term"].includes(standing) ? standing : "";
}

/** The same non-empty keys as an object: the body of a bulk action "by filter". */
export function registerFilterParams(values: RegisterFilterValues): Record<string, string> {
  return Object.fromEntries(new URLSearchParams(registerQuery(values)));
}

/** The server query string: only the keys that hold a value, in the contract's own names. */
export function registerQuery(values: RegisterFilterValues): string {
  const query = new URLSearchParams();
  for (const key of Object.keys(REGISTER_FILTER_DEFAULTS) as (keyof RegisterFilterValues)[]) {
    const value = (values[key] ?? "").trim();
    if (value) query.set(key, value);
  }
  return query.toString();
}

/** Filters besides the search and the chip, counted for the "Filters" button. */
export const activeRegisterFilters = (values: RegisterFilterValues) =>
  (Object.keys(values) as (keyof RegisterFilterValues)[]).filter((key) => key !== "q" && key !== "chip" && values[key]).length;

/** Words for a per-row bulk outcome code; unknown codes fall back to the code itself. */
export function rowResultLabel(code: string): string {
  switch (code) {
    case "": return t`Done`;
    case "not_found": return t`Not in your scope or no longer a member`;
    case "not_due": return t`Not due for a reminder today`;
    case "no_card": return t`Holds no card`;
    case "not_sent": return t`Card email not sent (limit or rule)`;
    case "quota_exceeded": return t`Limit reached`;
    case "permission_denied": return t`Not allowed`;
    default: return code.replace(/_/g, " ");
  }
}
