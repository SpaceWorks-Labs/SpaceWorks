import { t } from "@lingui/core/macro";

/** Translated wording for a waiver state on a booking arrival or event check-in. */
export function waiverStateLabel(state: string): string {
  switch (state) {
    case "not_required": return t`not required`;
    case "current":
    case "on_file": return t`on file`;
    case "missing": return t`missing`;
    default: return state.replace(/_/g, " ");
  }
}

/** Translated wording for why a queued offline check-in did not apply. */
export function offlineSyncOutcomeLabel(outcome: string): string {
  switch (outcome) {
    case "applied": return t`Checked in`;
    case "already_attended": return t`Already checked in`;
    case "duplicate_operation": return t`Already sent`;
    case "event_unavailable": return t`Event is not available`;
    case "invalid_token": return t`Ticket code not recognised`;
    case "outside_window": return t`Outside the check-in window`;
    case "registration_changed": return t`Registration changed since the roster was downloaded`;
    case "stage_incomplete": return t`A required stage form is not complete`;
    // EV-27: the minor-clearance re-check at check-in.
    case "guardian_consent_required": return t`A guardian's consent is needed first`;
    case "guardian_consent_expired": return t`The guardian's consent has expired`;
    case "guardian_terms_missing": return t`The guardian has not accepted the current terms`;
    case "minor_not_admitted": return t`This space does not admit people under the adult age`;
    case "minor_below_minimum_age": return t`Below this space's minimum age`;
    default: return outcome.replace(/_/g, " ");
  }
}
