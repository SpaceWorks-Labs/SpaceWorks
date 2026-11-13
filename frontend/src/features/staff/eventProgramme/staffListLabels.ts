import { t } from "@lingui/core/macro";
import { opsStatusLabel } from "../opsPresentation";

/** Translated names for the event staff lists, their filters and filter values (label maps are functions). */
export const listLabel = (key: string) => ({
  guests: t`Guests`, teams: t`Teams`, submissions: t`Submissions`, results: t`Results`, progress: t`Judging progress`,
} as Record<string, string>)[key] ?? key;

export const filterLabel = (key: string) => ({
  status: t`Status`, state: t`State`, triage: t`Eligibility`, below_target: t`Below the review target`,
  reply: t`Still coming?`, list: t`Check-in list`, collected: t`Collected`,
} as Record<string, string>)[key] ?? key;

export function optionLabel(filter: string, value: string) {
  if (filter === "status") return opsStatusLabel(value);
  const labels: Record<string, Record<string, string>> = {
    reply: { yes: t`Said yes`, no: t`Said no`, waiting: t`Not replied yet`, not_asked: t`Not asked` },
    collected: { yes: t`Collected`, no: t`Not collected yet` },
    below_target: { true: t`Yes` },
    triage: { pending: t`Not screened`, eligible: t`Eligible`, ineligible: t`Not eligible`, hidden: t`Hidden` },
    state: { forming: t`Forming`, locked: t`Locked`, disbanded: t`Disbanded`, draft: t`Draft`, submitted: t`Submitted`,
      under_review: t`Under review`, judged: t`Judged`, disqualified: t`Disqualified`, withdrawn: t`Withdrawn` },
  };
  return labels[filter]?.[value] ?? value.replace(/_/g, " ");
}
