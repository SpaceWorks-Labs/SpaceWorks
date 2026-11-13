import { t } from "@lingui/core/macro";

/** The server's closed reason vocabulary (`serializers_finance.REASONS`); free text goes in the note. */
export const REASON_CODES = ["approved", "policy_cap", "category_cap", "ineligible", "insufficient_evidence", "receipt_mismatch",
  "attendance_required", "need_based", "tier_award", "budget_available", "waitlisted", "declined", "information_required",
  "deadline_extension", "attendance_exception", "receipt_shared", "decision_correction", "no_liability", "other"] as const;
export type ReasonCode = typeof REASON_CODES[number];

export function reasonLabel(code: string): string {
  switch (code) {
    case "approved": return t`Approved as claimed`;
    case "policy_cap": return t`Limited by the policy cap`;
    case "category_cap": return t`Limited by a category cap`;
    case "ineligible": return t`Not eligible`;
    case "insufficient_evidence": return t`Not enough evidence`;
    case "receipt_mismatch": return t`Receipt does not match`;
    case "attendance_required": return t`Venue attendance required`;
    case "need_based": return t`Based on need`;
    case "tier_award": return t`Policy tier`;
    case "budget_available": return t`Budget available`;
    case "waitlisted": return t`Waitlisted`;
    case "declined": return t`Declined`;
    case "information_required": return t`More information needed`;
    case "deadline_extension": return t`Deadline extended`;
    case "attendance_exception": return t`Attendance exception`;
    case "receipt_shared": return t`Receipt shared across claims`;
    case "decision_correction": return t`Decision correction`;
    case "no_liability": return t`Nothing owed`;
    case "other": return t`Other (explain in the note)`;
    default: return code.replace(/_/g, " ");
  }
}

/** A select over the closed reason list; forwards the label wiring a surrounding Field adds. */
export function ReasonSelect({ value, onChange, ...aria }: { value: string; onChange: (value: ReasonCode) => void;
  "aria-labelledby"?: string; "aria-describedby"?: string }) {
  return <select {...aria} className="desk-input" required value={value} onChange={event => onChange(event.target.value as ReasonCode)}>
    <option value="">{t`Choose a reason…`}</option>
    {REASON_CODES.map(code => <option key={code} value={code}>{reasonLabel(code)}</option>)}
  </select>;
}
