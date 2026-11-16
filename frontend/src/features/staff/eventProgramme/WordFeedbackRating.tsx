export const FEEDBACK_WORDS = ["Excellent", "Good", "Okay", "Poor"] as const;
export type FeedbackWord = typeof FEEDBACK_WORDS[number];
type LegacyProps = {
  schemaVersion: 1; values: Record<FeedbackWord, number | string>;
  value: number | string | undefined; onChange: (value: number | string) => void;
};
type V2Props = {
  schemaVersion: 2; values: Record<FeedbackWord, string>;
  value: { option_id: string } | undefined; onChange: (value: { option_id: string }) => void;
};
/** The caller supplies that revision's option mapping. Never guess a historical numeric scale. */
export function WordFeedbackRating(props: (LegacyProps | V2Props) & { id: string; label: string; required?: boolean; disabled?: boolean }) {
  return <fieldset className="grid gap-3" disabled={props.disabled}><legend className="mb-2 text-sm font-semibold">{props.label}{props.required ? " (required)" : ""}</legend><div className="grid gap-3 sm:grid-cols-4">{FEEDBACK_WORDS.map(word => {
    const selected = props.schemaVersion === 1 ? props.value === props.values[word] : props.value?.option_id === props.values[word];
    return <label key={word} className={`flex min-h-11 items-center gap-3 rounded-xl border p-3 text-sm ${selected ? "border-brand bg-brand text-on-brand" : "border-line bg-panel text-ink"}`}><input type="radio" name={props.id} required={props.required} checked={selected} aria-label={`${word}${selected ? ", selected" : ""}`} onChange={() => { if (props.schemaVersion === 1) props.onChange(props.values[word]); else props.onChange({ option_id: props.values[word] }); }} />{word}</label>;
  })}</div></fieldset>;
}
