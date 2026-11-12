import { t } from "@lingui/core/macro";

const plain = (value: string) => value.replace(/_/g, " ");

/** Translated wording for a project submission `state`. */
export function submissionStateLabel(state: string): string {
  switch (state) {
    case "draft": return t`Draft`;
    case "submitted": return t`Submitted`;
    case "locked": return t`Locked`;
    case "withdrawn": return t`Withdrawn`;
    case "disqualified": return t`Disqualified`;
    default: return plain(state);
  }
}

/** Translated wording for an uploaded asset `state`. */
export function assetStateLabel(state: string): string {
  switch (state) {
    case "reserved": return t`Reserved`;
    case "uploaded": return t`Uploaded`;
    case "validating": return t`Checking`;
    case "copying": return t`Copying`;
    case "ready": return t`Ready`;
    case "deleting": return t`Deleting`;
    case "rejected": return t`Rejected`;
    default: return plain(state);
  }
}

/** Translated wording for a project eligibility `triage` value. */
export function triageLabel(value: string): string {
  switch (value) {
    case "pending": return t`Pending`;
    case "eligible": return t`Eligible`;
    case "ineligible": return t`Ineligible`;
    case "hidden": return t`Hidden`;
    default: return plain(value);
  }
}
