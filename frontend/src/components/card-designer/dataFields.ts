// The data fields a card may place (apps/card_designs/data_fields.py) and the sample
// people the designer previews: a typical name and a long one, to test fitting.

export const DATA_FIELDS: { key: string; label: string }[] = [
  { key: "name", label: "Name" }, { key: "number", label: "Number" }, { key: "plan", label: "Plan or programme" },
  { key: "valid_until", label: "Valid until" }, { key: "member_since", label: "Member since" },
  { key: "role", label: "Role" }, { key: "title", label: "Title" }, { key: "team", label: "Team" },
  { key: "track", label: "Track" }, { key: "event", label: "Event" }, { key: "space", label: "Space" },
  { key: "organisation", label: "Organisation" }, { key: "programme", label: "Programme" },
  { key: "issued_on", label: "Issued on" }, { key: "verify_url", label: "Check link" },
  { key: "certifications", label: "Certifications" },
  { key: "blood_group", label: "Blood group (holder opt-in)" },
  { key: "emergency_contact", label: "Emergency contact (holder opt-in)" },
];

/** The built-in fields plus a design's own answer fields (programme questions). */
export function fieldsFor(answers: { key: string; label: string }[] = []) {
  return [...DATA_FIELDS, ...answers.map((answer) => ({ key: answer.key, label: `Answer: ${answer.label}` }))];
}

export const SAMPLE_SHORT: Record<string, string> = {
  name: "Priya Raman", number: "TNK-0042", plan: "Monthly", valid_until: "31 Dec 2026", member_since: "Mar 2024",
  role: "Member", title: "Treasurer", team: "Night Owls", track: "Hardware", event: "Spring Build Night",
  space: "Tinkerspace", organisation: "Makers Guild", programme: "Student ID", issued_on: "2 Nov 2026",
  verify_url: "example.org/verify/c/…", certifications: "Laser induction", blood_group: "O+",
  emergency_contact: "Arjun · 98765 43210",
};

export const SAMPLE_LONG: Record<string, string> = {
  ...SAMPLE_SHORT, name: "Alexandra Montgomery-Fitzgerald", plan: "Annual supporting member (concession)",
  title: "Senior Community Partnerships Lead", team: "The Midnight Debugging Collective",
  event: "Community Hardware Hackathon 2026", space: "Thiruvananthapuram Community Makerspace",
  organisation: "International Federation of Community Builders",
};

export function merge(text: string, values: Record<string, string>) {
  return text.replace(/{{\s*([^{}]*?)\s*}}/g, (_match, tag: string) => values[tag] ?? (tag.startsWith("field:") ? "Sample answer" : ""));
}
