import { t } from "@lingui/core/macro";
// The data fields a card may place (apps/card_designs/data_fields.py) and the sample
// people the designer previews: a typical name and a long one, to test fitting.

export const DATA_FIELDS: { key: string; label: string }[] = [
  { key: "name", label: t`Name` }, { key: "number", label: t`Number` }, { key: "plan", label: t`Plan or programme` },
  { key: "valid_until", label: t`Valid until` }, { key: "member_since", label: t`Member since` },
  { key: "role", label: t`Role` }, { key: "title", label: t`Title` }, { key: "team", label: t`Team` },
  { key: "track", label: t`Track` }, { key: "event", label: t`Event` }, { key: "space", label: t`Space` },
  { key: "organisation", label: t`Organisation` }, { key: "programme", label: t`Programme` },
  { key: "issued_on", label: t`Issued on` }, { key: "verify_url", label: t`Check link` },
  { key: "certifications", label: t`Certifications` },
  { key: "blood_group", label: t`Blood group (holder opt-in)` },
  { key: "emergency_contact", label: t`Emergency contact (holder opt-in)` },
];

/** The built-in fields plus a design's own answer fields (programme questions). */
export function fieldsFor(answers: { key: string; label: string }[] = []) {
  return [...DATA_FIELDS, ...answers.map((answer) => ({ key: answer.key, label: t`Answer: ${answer.label}` }))];
}

export const SAMPLE_SHORT: Record<string, string> = {
  name: "Priya Raman", number: "TNK-0042", plan: "Monthly", valid_until: "31 Dec 2026", member_since: "Mar 2024",
  role: "Member", title: t`Treasurer`, team: "Night Owls", track: "Hardware", event: "Spring Build Night",
  space: "Tinkerspace", organisation: "Makers Guild", programme: "Student ID", issued_on: "2 Nov 2026",
  verify_url: "example.org/verify/c/…", certifications: "Laser induction", blood_group: "O+",
  emergency_contact: "Arjun · 98765 43210",
};

export const SAMPLE_LONG: Record<string, string> = {
  ...SAMPLE_SHORT, name: "Alexandra Montgomery-Fitzgerald", plan: "Annual supporting member (concession)",
  title: t`Senior Community Partnerships Lead`, team: "The Midnight Debugging Collective",
  event: "Community Hardware Hackathon 2026", space: "Thiruvananthapuram Community Makerspace",
  organisation: "International Federation of Community Builders",
};

export function merge(text: string, values: Record<string, string>) {
  return text.replace(/{{\s*([^{}]*?)\s*}}/g, (_match, tag: string) => values[tag] ?? (tag.startsWith("field:") ? "Sample answer" : ""));
}
