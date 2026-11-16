import { t } from "@lingui/core/macro";

const humanize = (value: string) => value.replace(/_/g, " ");

/** Translated name of a v2 form question type. */
export function questionTypeLabel(type: string): string {
  switch (type) {
    case "short_text": return t`Short text`;
    case "long_text": return t`Long text`;
    case "number": return t`Number`;
    case "date": return t`Date`;
    case "date_of_birth": return t`Date of birth`;
    case "single_choice": return t`Single choice`;
    case "multi_choice": return t`Multiple choice`;
    case "yes_no": return t`Yes / No`;
    case "email": return t`Email`;
    case "phone": return t`Phone`;
    case "url": return t`Web address`;
    case "asset_reference": return t`Equipment reference`;
    case "age_at_event": return t`Age at the event`;
    case "emergency_contact": return t`Emergency contact`;
    case "money": return t`Amount of money`;
    case "file": return t`File upload`;
    case "itinerary": return t`Travel itinerary`;
    default: return humanize(type);
  }
}

/** Translated name of what an uploaded form file is for. */
export function filePurposeLabel(purpose: string): string {
  switch (purpose) {
    case "stage_form_file": return t`stage form file`;
    case "reimbursement_receipt": return t`expense receipt`;
    case "reimbursement_payee_document": return t`payee document`;
    default: return humanize(purpose);
  }
}

/** Translated label for a question's numeric limit field. */
export function questionBoundLabel(key: string): string {
  switch (key) {
    case "max_length": return t`Maximum length`;
    case "min_length": return t`Minimum length`;
    case "min": return t`Minimum`;
    case "max": return t`Maximum`;
    case "min_selections": return t`Minimum selections`;
    case "max_selections": return t`Maximum selections`;
    case "other_max_length": return t`Maximum length of "Other"`;
    default: return humanize(key);
  }
}
