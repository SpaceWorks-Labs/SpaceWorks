import { t } from "@lingui/core/macro";
import { useId } from "react";

export type FeedbackWord = "excellent" | "good" | "okay" | "poor";
function wordLabel(word: FeedbackWord) {
  switch (word) {
    case "excellent": return t`Excellent`;
    case "good": return t`Good`;
    case "okay": return t`Okay`;
    case "poor": return t`Poor`;
  }
}
/** Numeric legacy answers are displayed by their own schema, never reinterpreted as words. */
export function WordFeedback({ version, value, onChange }: {
  version: "words_v1" | "legacy_numeric"; value: FeedbackWord | number | null; onChange: (value: FeedbackWord) => void;
}) {
  const id = useId();
  if (version === "legacy_numeric") return <p className="text-muted">{value != null ? t`Recorded rating: ${value}` : t`Recorded rating: Not answered`}</p>;
  return <fieldset><legend className="mb-2 font-medium text-ink">{t`How was your experience?`}</legend>
    <div className="flex flex-wrap gap-2">{(["excellent", "good", "okay", "poor"] as const).map(word => <label key={word} className="desk-button gap-2">
      <input type="radio" name={id} value={word} checked={value === word} onChange={() => onChange(word)}
        className="h-4 w-4 accent-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" />
      {wordLabel(word)}
    </label>)}</div>
  </fieldset>;
}
