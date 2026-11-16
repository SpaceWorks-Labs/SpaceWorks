// Sample people for the badge designer: a typical name and a long one, to test fitting (as in Events).
import { t } from "@lingui/core/macro";

import { SAMPLE_LONG, SAMPLE_SHORT } from "../../../components/card-designer/dataFields";
import { fieldTag } from "./badgeCompile";

export type Sample = "short" | "long";
export const SAMPLE_QR_VALUE = "preview-check-in-token";

function sampleAnswer(label: string, long: boolean) {
  if (/organi[sz]ation|company|employer|school|university|college/i.test(label)) {
    return long ? t`International Federation of Community Builders` : t`Tech4Good`;
  }
  if (/role|title|position|job/i.test(label)) return long ? t`Senior Community Partnerships Lead` : t`Designer`;
  if (/diet|food|meal/i.test(label)) return t`Vegetarian`;
  if (/size|shirt/i.test(label)) return t`M`;
  if (/pronoun/i.test(label)) return t`she/her`;
  return long ? t`A longer sample answer` : t`Sample answer`;
}

/** Merge values for every tag a badge can print, with an answer for each registration question. */
export function sampleValues(fields: { key: string; label: string }[], sample: Sample): Record<string, string> {
  const long = sample === "long";
  const values: Record<string, string> = {
    ...(long ? SAMPLE_LONG : SAMPLE_SHORT),
    // i18n-ignore: placeholder email addresses, not copy
    email: long ? "alexandra.montgomery-fitzgerald@example.com" : "priya@example.com",
    crew_kind: t`Volunteer`,
  };
  for (const field of fields) {
    const tag = fieldTag(field.key);
    if (tag?.startsWith("field:")) values[tag] = sampleAnswer(field.label, long);
  }
  return values;
}
