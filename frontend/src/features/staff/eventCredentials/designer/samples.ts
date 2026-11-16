import { t } from "@lingui/core/macro";
// Sample values the designer canvas prints in place of merge tags. The server preview uses the
// same sample name and the kind's frozen labels, so the two agree on what fits.

export const SAMPLE_NAMES = [
  { key: "short", label: t`Short`, value: t`Priya Raman` },
  { key: "long", label: t`Long`, value: t`Alexandra Montgomery-Fitzgerald` },
  { key: "malayalam", label: t`Malayalam`, value: "അനന്തകൃഷ്ണൻ നായർ" },
  { key: "arabic", label: t`Arabic`, value: "محمد عبد الله" },
] as const;

export const CERTIFICATE_KINDS = [
  { value: "attendance", label: t`Attendance`, role: "Attendee", award: "", place: "" },
  { value: "participant", label: t`Participant`, role: "Participant", award: "", place: "" },
  { value: "finalist", label: t`Finalist`, role: "Participant", award: "Finalist · Best hardware hack", place: "" },
  { value: "winner", label: t`Winner`, role: "Participant", award: "1st place · Best hardware hack", place: "1st place" },
  { value: "volunteer_thanks", label: t`Volunteer`, role: "Volunteer", award: "", place: "" },
  { value: "mentor_thanks", label: t`Mentor`, role: "Mentor", award: "", place: "" },
  { value: "judge_thanks", label: t`Judge`, role: "Judge", award: "", place: "" },
  { value: "organiser_thanks", label: t`Organiser`, role: "Organiser", award: "", place: "" },
] as const;
export type CertificateKind = typeof CERTIFICATE_KINDS[number]["value"];

/** Merge values for the canvas. `kind` "" is the event default design (shown as attendance). */
export function certificateSampleValues(name: string, kind: CertificateKind | ""): Record<string, string> {
  const row = CERTIFICATE_KINDS.find((item) => item.value === (kind || "attendance")) ?? CERTIFICATE_KINDS[0];
  return { name, kind: row.label, award: row.award, role: row.role, place: row.place, crewRole: row.role,
    event: "Spring Build Night", eventDate: "18 October 2026", organisation: "Tinkerspace", issueDate: "20 October 2026" };
}

export const SIGNATURE_SAMPLES: Record<number, { name: string; title: string }> = {
  1: { name: "Signatory name", title: t`Director` }, 2: { name: "Second signatory", title: t`Programme lead` },
  3: { name: "Third signatory", title: t`Partner` },
};
