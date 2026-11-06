// Sample values the designer canvas prints in place of merge tags. The server preview uses the
// same sample name and the kind's frozen labels, so the two agree on what fits.

export const SAMPLE_NAMES = [
  { key: "short", label: "Short", value: "Priya Raman" },
  { key: "long", label: "Long", value: "Alexandra Montgomery-Fitzgerald" },
  { key: "malayalam", label: "Malayalam", value: "അനന്തകൃഷ്ണൻ നായർ" },
  { key: "arabic", label: "Arabic", value: "محمد عبد الله" },
] as const;

export const CERTIFICATE_KINDS = [
  { value: "attendance", label: "Attendance", role: "Attendee", award: "", place: "" },
  { value: "participant", label: "Participant", role: "Participant", award: "", place: "" },
  { value: "finalist", label: "Finalist", role: "Participant", award: "Finalist · Best hardware hack", place: "" },
  { value: "winner", label: "Winner", role: "Participant", award: "1st place · Best hardware hack", place: "1st place" },
  { value: "volunteer_thanks", label: "Volunteer", role: "Volunteer", award: "", place: "" },
  { value: "mentor_thanks", label: "Mentor", role: "Mentor", award: "", place: "" },
  { value: "judge_thanks", label: "Judge", role: "Judge", award: "", place: "" },
  { value: "organiser_thanks", label: "Organiser", role: "Organiser", award: "", place: "" },
] as const;
export type CertificateKind = typeof CERTIFICATE_KINDS[number]["value"];

/** Merge values for the canvas. `kind` "" is the event default design (shown as attendance). */
export function certificateSampleValues(name: string, kind: CertificateKind | ""): Record<string, string> {
  const row = CERTIFICATE_KINDS.find((item) => item.value === (kind || "attendance")) ?? CERTIFICATE_KINDS[0];
  return { name, kind: row.label, award: row.award, role: row.role, place: row.place, crewRole: row.role,
    event: "Spring Build Night", eventDate: "18 October 2026", organisation: "Tinkerspace", issueDate: "20 October 2026" };
}

export const SIGNATURE_SAMPLES: Record<number, { name: string; title: string }> = {
  1: { name: "Signatory name", title: "Director" }, 2: { name: "Second signatory", title: "Programme lead" },
  3: { name: "Third signatory", title: "Partner" },
};
