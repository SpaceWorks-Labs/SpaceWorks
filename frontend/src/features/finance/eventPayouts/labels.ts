import { t } from "@lingui/core/macro";

/** Translated wording for a payout obligation `state`. */
export function payoutStateLabel(state: string): string {
  switch (state) {
    case "open": return t`Open`;
    case "settled": return t`Settled`;
    case "cancelled": return t`Cancelled`;
    default: return state.replace(/_/g, " ");
  }
}

/** Translated wording for a payout obligation `eligibility_status`. */
export function payoutEligibilityLabel(status: string): string {
  switch (status) {
    case "eligible": return t`Eligible`;
    case "held": return t`Held`;
    case "needs_acknowledgement": return t`Needs acknowledgement`;
    default: return status.replace(/_/g, " ");
  }
}

/** Translated wording for a decision revision `kind`. */
export function decisionKindLabel(kind: string): string {
  return kind === "decision" ? t`Decision` : kind === "cancellation" ? t`Cancellation` : kind.replace(/_/g, " ");
}

/** A finance hold line, "Eligibility hold" or "Retention hold". */
export function holdKindLabel(kind: string): string {
  return kind === "eligibility" ? t`Eligibility hold` : kind === "retention" ? t`Retention hold` : t`Hold`;
}

/** A staff-entered reason code (lowercase letters, digits and underscores), shown as typed with spaces. */
export function reasonCodeText(code: string): string {
  return code.replace(/_/g, " ");
}

/** Translated label for a field in frozen payout decision or eligibility evidence. */
export function evidenceFieldLabel(key: string): string {
  return ({
    schema_version: t`Format version`, source: t`Source`, claim_uuid: t`Claim reference`, claim_revision: t`Claim revision`,
    decision_uuid: t`Decision reference`, decision_sequence: t`Decision number`, decision: t`Decision`, outcome: t`Outcome`,
    decided_at: t`Decided at`, actor_id: t`Decided by (user ID)`, reason_code: t`Reason code`, reason: t`Reason`,
    award: t`Award`, uuid: t`Reference`, cap_minor: t`Cap (minor units)`, currency: t`Currency`,
    policy_revision: t`Policy revision`, rule_revision: t`Rule revision`, applied_rules: t`Applied rules`,
    category_caps: t`Category caps`, totals: t`Totals`, claimed_minor: t`Claimed (minor units)`,
    eligible_minor: t`Eligible (minor units)`, approved_minor: t`Approved (minor units)`, lines: t`Expense lines`,
    line_uuid: t`Line reference`, category: t`Category`, expense_date: t`Expense date`, vendor: t`Vendor`,
    description: t`Description`, traveller: t`Traveller`, original_amount_minor: t`Original amount (minor units)`,
    original_currency: t`Original currency`, original_exponent: t`Original currency decimals`, fx_rate: t`Exchange rate`,
    rate_date: t`Rate date`, rate_source: t`Rate source`, source_note: t`Source note`, target_exponent: t`Currency decimals`,
    converted_minor: t`Converted (minor units)`, limits: t`Limits`, rounding: t`Rounding`, receipt: t`Receipt`,
    attachment_id: t`Attachment ID`, generation: t`File version`, sha256: t`File checksum`, total_minor: t`Receipt total (minor units)`,
    receipt_use_id: t`Receipt use ID`, receipt_use_version: t`Receipt use version`, allocation_minor: t`Allocated (minor units)`,
    override_uuid: t`Override reference`, override_allocation: t`Override allocation`, override_reason_code: t`Override reason code`,
    override_reason: t`Override reason`, eligibility: t`Eligibility`, registration_id: t`Registration ID`,
    attendance_revision: t`Attendance revision`, checkin_event_id: t`Check-in record ID`, correction_watermark: t`Corrections applied through`,
    attestation_uuid: t`Attestation reference`, project_snapshot_ref: t`Project snapshot`, core_eligibility_revision: t`Eligibility revision`,
  } as Record<string, string>)[key] ?? key.replace(/_/g, " ");
}
