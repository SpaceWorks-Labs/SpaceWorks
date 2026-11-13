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
  // E-B2: ticket merge fields.
  { key: "date", label: t`Event date` }, { key: "time", label: t`Event time` }, { key: "venue", label: t`Venue` },
  { key: "price", label: t`Price` }, { key: "order", label: t`Order number` },
  // O-B4: member units and staff ID cards.
  { key: "unit", label: t`Unit` }, { key: "unit_code", label: t`Unit code` }, { key: "units", label: t`Unit path` },
  { key: "level1", label: t`Unit level 1` }, { key: "level2", label: t`Unit level 2` },
  { key: "level3", label: t`Unit level 3` }, { key: "level4", label: t`Unit level 4` },
  { key: "roles", label: t`Roles` }, { key: "machine_scope", label: t`Machine scope` },
  // Card Studio: the name split, for two-weight names (a light first name over a bold last name).
  { key: "first_name", label: t`First name` }, { key: "last_name", label: t`Last name` },
];

// Where a tag makes sense; tags not listed fit every card. The server accepts any tag on any design.
const ONLY_ON: Record<string, string[]> = {
  date: ["event_ticket"], time: ["event_ticket"], venue: ["event_ticket"], price: ["event_ticket"], order: ["event_ticket"],
  unit: ["member_cards", "staff_cards"], unit_code: ["member_cards", "staff_cards"], units: ["member_cards", "staff_cards"],
  level1: ["member_cards", "staff_cards"], level2: ["member_cards", "staff_cards"], level3: ["member_cards", "staff_cards"],
  level4: ["member_cards", "staff_cards"], roles: ["staff_cards"], machine_scope: ["staff_cards"],
};

/** The built-in fields plus a design's own answer fields (programme questions). */
export function fieldsFor(answers: { key: string; label: string }[] = [], domain?: string) {
  const fits = (key: string) => !domain || !ONLY_ON[key] || ONLY_ON[key].includes(domain);
  return [...DATA_FIELDS.filter((field) => fits(field.key)), ...answers.map((answer) => ({ key: answer.key, label: t`Answer: ${answer.label}` }))];
}

export const SAMPLE_SHORT: Record<string, string> = {
  // i18n-ignore: sample person, number, dates, URL and contact are placeholder data, not copy
  name: "Priya Raman", number: "TNK-0042", valid_until: "31 Dec 2026", member_since: "Mar 2024", issued_on: "2 Nov 2026",
  // i18n-ignore: placeholder data (see above)
  verify_url: "example.org/verify/c/…", blood_group: "O+", emergency_contact: "Arjun · 98765 43210",
  // i18n-ignore: placeholder data (see above)
  email: "priya@example.com", date: "14 Nov 2026", time: "10:00 – 17:00", price: "INR 500", order: "ORD-1042",
  // i18n-ignore: placeholder data (see above)
  unit_code: "KOC", level1: "North", level2: "Kochi", level3: "", level4: "",
  unit: t`Kochi`, units: t`North / Kochi`, crew_kind: t`Volunteer`, venue: t`Tinkerspace, Main Hall`,
  roles: t`Technician`, machine_scope: t`Laser cutters`,
  first_name: "Priya", last_name: "Raman", // i18n-ignore: placeholder name
  plan: t`Monthly`, role: t`Member`, title: t`Treasurer`, team: t`Night Owls`, track: t`Hardware`, event: t`Spring Build Night`,
  space: t`Tinkerspace`, organisation: t`Makers Guild`, programme: t`Student ID`, certifications: t`Laser induction`,
};

export const SAMPLE_LONG: Record<string, string> = {
  // i18n-ignore: placeholder person name
  ...SAMPLE_SHORT, name: "Alexandra Montgomery-Fitzgerald", first_name: "Alexandra", last_name: "Montgomery-Fitzgerald",
  plan: t`Annual supporting member (concession)`,
  title: t`Senior Community Partnerships Lead`, team: t`The Midnight Debugging Collective`,
  event: t`Community Hardware Hackathon 2026`, space: t`Thiruvananthapuram Community Makerspace`,
  organisation: t`International Federation of Community Builders`,
  email: "alexandra.montgomery-fitzgerald@example.com", // i18n-ignore: placeholder data
  units: t`Northern Region / Greater Thiruvananthapuram Chapter`, roles: t`Space Manager, Technician, Event Manager`,
  machine_scope: t`Laser cutters, 3D printers and 4 more`,
};

/** The holder's name split at the first space, like the server's `first_name` / `last_name` tags. */
export function nameParts(name: string | undefined) {
  const [first, ...rest] = (name ?? "").trim().split(" ");
  return { first_name: first ?? "", last_name: rest.join(" ").trim() };
}

export function merge(text: string, values: Record<string, string>) {
  return text.replace(/{{\s*([^{}]*?)\s*}}/g, (_match, tag: string) => values[tag]
    ?? (tag === "first_name" || tag === "last_name" ? nameParts(values.name)[tag]
      : tag.startsWith("field:") ? "Sample answer" : ""));
}
