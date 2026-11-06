// Who the designer draws the card for: a short or long sample name, or one real holder of a
// card this design prints (their name and number; every other field stays a sample).
import { SAMPLE_LONG, SAMPLE_SHORT } from "./dataFields";
import type { CardHolder } from "./designerHistoryApi";

export type PreviewPerson = { kind: "short" } | { kind: "long" } | { kind: "holder"; holder: CardHolder };

export function previewValues(person: PreviewPerson): Record<string, string> {
  if (person.kind === "long") return SAMPLE_LONG;
  if (person.kind === "holder") {
    return { ...SAMPLE_SHORT, name: person.holder.name || SAMPLE_SHORT.name, number: person.holder.number || SAMPLE_SHORT.number };
  }
  return SAMPLE_SHORT;
}

export function previewLabel(person: PreviewPerson) {
  if (person.kind === "long") return `${SAMPLE_LONG.name} (long sample)`;
  if (person.kind === "holder") return person.holder.name || "Hidden name";
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
