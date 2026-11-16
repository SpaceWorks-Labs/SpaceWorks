import { t } from "@lingui/core/macro";

import type { TemplateSpec } from "./templatesApi";

export const SPEC_SECTIONS = ["basics", "consumables", "intake_fields", "pricing", "access", "bookings", "safety", "maintenance", "job", "notifications", "documents"] as const;
export type SpecSection = typeof SPEC_SECTIONS[number];
export type SpecProblems = Partial<Record<SpecSection, string>>;

const KEY = /^[a-z][a-z0-9_]{0,49}$/;
export const keyOk = (key: string) => KEY.test(key) && !key.endsWith("_id");
const inRange = (value: number | undefined, min: number, max: number) => value === undefined || (Number.isInteger(value) && value >= min && value <= max);

function keyProblem(keys: string[], what: string): string {
  const seen = new Set<string>();
  for (const key of keys) {
    if (!keyOk(key)) return t`A ${what} key starts with a letter and uses only lowercase letters, digits and underscores, up to 50 characters, and cannot end in _id.`;
    if (seen.has(key)) return t`Two ${what}s use the key ${key}.`;
    seen.add(key);
  }
  return "";
}

/** The limits the server enforces (`template_spec.py`), checked before a save so a mistake is shown in the section that holds it. */
export function validateSpec(spec: TemplateSpec): SpecProblems {
  const problems: SpecProblems = {};
  if (spec.consumables.length > 30) problems.consumables = t`A template holds at most 30 consumables.`;
  else if (spec.consumables.some(row => !row.name?.trim())) problems.consumables = t`Every consumable needs a name.`;
  else problems.consumables = keyProblem(spec.consumables.map(row => row.key ?? ""), t`consumable`) || undefined;
  if (spec.intake_fields.length > 20) problems.intake_fields = t`A template holds at most 20 intake fields.`;
  else if (spec.intake_fields.some(field => !field.label.trim())) problems.intake_fields = t`Every field needs a label.`;
  else if (spec.intake_fields.some(field => field.type === "choice" && !field.choices?.length)) problems.intake_fields = t`A choice field needs at least one choice.`;
  else problems.intake_fields = keyProblem(spec.intake_fields.map(field => field.key), t`field`) || undefined;
  if (spec.maintenance.length > 20) problems.maintenance = t`A template holds at most 20 maintenance items.`;
  else if (spec.maintenance.some(item => !item.title.trim())) problems.maintenance = t`Every maintenance item needs a title.`;
  else if (spec.maintenance.some(item => !inRange(item.interval, 1, 100000))) problems.maintenance = t`A maintenance interval is a whole number from 1 to 100000.`;
  const book = spec.bookings;
  if (!inRange(book.slot_minutes, 1, 1440) || !inRange(book.buffer_minutes, 0, 1440)) problems.bookings = t`Slot length is 1 to 1440 minutes and the buffer is 0 to 1440.`;
  const safety = spec.safety;
  if (!inRange(safety.idle_auto_off_minutes, 1, 1440) || !inRange(safety.max_session_minutes, 1, 1440)) problems.safety = t`Idle switch-off and longest session are 1 to 1440 minutes.`;
  if (spec.documents.training_notes.length > 10000) problems.documents = t`Training notes can be at most 10000 characters.`;
  return Object.fromEntries(Object.entries(problems).filter(([, text]) => text)) as SpecProblems;
}

/** Which section a server refusal is about, found from the field name it quotes; null when it names none. */
export function sectionOfMessage(message: string | undefined): SpecSection | null {
  if (!message) return null;
  let best: { section: SpecSection; at: number } | null = null;
  for (const section of SPEC_SECTIONS) {
    const at = message.search(new RegExp(`\\b${section}\\b`));
    if (at >= 0 && (!best || at < best.at)) best = { section, at };
  }
  if (!best && /\bintake\b/.test(message)) return "intake_fields";
  return best?.section ?? null;
}
