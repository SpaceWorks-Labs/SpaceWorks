// Who the designer draws the card for: a sample person (the owner's own sample and neutral names, each with a
// short and a long form), or one real holder of a card this design prints (their name and number; every
// other field stays a sample).
import { t } from "@lingui/core/macro";
import { nameParts, SAMPLE_LONG, SAMPLE_SHORT } from "./dataFields";
import type { CardHolder } from "./designerHistoryApi";

export type SamplePersonId = "owner" | "alex" | "sam";
export type PreviewPerson = { kind: "short" } | { kind: "long" } | { kind: "holder"; holder: CardHolder }
  | { kind: "sample"; id: SamplePersonId; long: boolean };

/** Sample names: placeholder data, not copy. The owner's own sample is the reference the studio recreates styles with. */
export const SAMPLE_PEOPLE: { id: SamplePersonId; label: string; short: string; long: string; role: string }[] = [
  { id: "owner", label: t`Shaan Shoukath (owner sample)`, short: "Shaan Shoukath", long: "Shaan Shoukath Abdul Rahman", role: "Founder" }, // i18n-ignore: placeholder name
  { id: "alex", label: t`Alex Morgan`, short: "Alex Morgan", long: "Alexandra Montgomery-Fitzgerald", role: "Member" }, // i18n-ignore: placeholder name
  { id: "sam", label: t`Sam Rivera`, short: "Sam Rivera", long: "Samuel Rivera-Hernandez de la Cruz", role: "Volunteer" }, // i18n-ignore: placeholder name
];

export function previewValues(person: PreviewPerson): Record<string, string> {
  if (person.kind === "long") return SAMPLE_LONG;
  if (person.kind === "sample") {
    const found = SAMPLE_PEOPLE.find((item) => item.id === person.id) ?? SAMPLE_PEOPLE[0];
    const name = person.long ? found.long : found.short;
    return { ...(person.long ? SAMPLE_LONG : SAMPLE_SHORT), name, ...nameParts(name), role: found.role };
  }
  if (person.kind === "holder") {
    const name = person.holder.name || SAMPLE_SHORT.name;
    return { ...SAMPLE_SHORT, name, ...nameParts(name), number: person.holder.number || SAMPLE_SHORT.number };
  }
  return SAMPLE_SHORT;
}

export function previewLabel(person: PreviewPerson) {
  if (person.kind === "long") return t`${SAMPLE_LONG.name} (long sample)`;
  if (person.kind === "sample") {
    const found = SAMPLE_PEOPLE.find((item) => item.id === person.id) ?? SAMPLE_PEOPLE[0];
    return person.long ? t`${found.long} (long sample)` : t`${found.short} (sample)`;
  }
  if (person.kind === "holder") return person.holder.name || t`Hidden name`;
  return `${SAMPLE_SHORT.name} (sample)`;
}

/** Client-side search over the returned holders: name, number or label, any word order. */
export function filterHolders(holders: CardHolder[], query: string) {
  const words = query.toLocaleLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return holders;
  return holders.filter((holder) => {
    const haystack = `${holder.name} ${holder.number} ${holder.label}`.toLocaleLowerCase();
    return words.every((word) => haystack.includes(word));
  });
}

/** Does this preview use the long-name form (the server renders its own long samples)? */
export const isLongPerson = (person: PreviewPerson) => person.kind === "long" || (person.kind === "sample" && person.long);
