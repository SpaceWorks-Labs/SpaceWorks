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
  // E-F1 (append-only): event badges print the holder's email and crew kind.
  { key: "email", label: t`Email` }, { key: "crew_kind", label: t`Crew kind` },
];

/** The built-in fields plus a design's own answer fields (programme questions). */
export function fieldsFor(answers: { key: string; label: string }[] = []) {
  return [...DATA_FIELDS, ...answers.map((answer) => ({ key: answer.key, label: t`Answer: ${answer.label}` }))];
}

export const SAMPLE_SHORT: Record<string, string> = {
  // i18n-ignore: sample person, number, dates, URL and contact are placeholder data, not copy
  name: "Priya Raman", number: "TNK-0042", valid_until: "31 Dec 2026", member_since: "Mar 2024", issued_on: "2 Nov 2026",
  // i18n-ignore: placeholder data (see above)
  verify_url: "example.org/verify/c/…", blood_group: "O+", emergency_contact: "Arjun · 98765 43210",
  plan: t`Monthly`, role: t`Member`, title: t`Treasurer`, team: t`Night Owls`, track: t`Hardware`, event: t`Spring Build Night`,
  space: t`Tinkerspace`, organisation: t`Makers Guild`, programme: t`Student ID`, certifications: t`Laser induction`,
};

export const SAMPLE_LONG: Record<string, string> = {
  // i18n-ignore: placeholder person name
  ...SAMPLE_SHORT, name: "Alexandra Montgomery-Fitzgerald",
  plan: t`Annual supporting member (concession)`,
  title: t`Senior Community Partnerships Lead`, team: t`The Midnight Debugging Collective`,
  event: t`Community Hardware Hackathon 2026`, space: t`Thiruvananthapuram Community Makerspace`,
  organisation: t`International Federation of Community Builders`,
};

export function merge(text: string, values: Record<string, string>) {
  return text.replace(/{{\s*([^{}]*?)\s*}}/g, (_match, tag: string) => values[tag] ?? (tag.startsWith("field:") ? "Sample answer" : ""));
}
