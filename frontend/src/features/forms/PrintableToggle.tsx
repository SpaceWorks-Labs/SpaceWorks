import { t } from "@lingui/core/macro";
import { useId } from "react";

import { printableAllowed } from "./sections";
import type { Question } from "./types";

/**
 * Parity O-B4: mark a membership join question so its answer may print on the member card. Only a
 * plain, non-sensitive answer qualifies (the server refuses the rest), so the box explains why it is
 * unavailable instead of disappearing.
 */
export function PrintableToggle({ question, onChange }: { question: Question; onChange: (printable: boolean) => void }) {
  const hintId = useId();
  const allowed = printableAllowed(question);
  return <div className="grid gap-1">
    <label className="flex min-h-11 items-center gap-3 text-sm">
      <input type="checkbox" aria-describedby={hintId} disabled={!allowed} checked={allowed && Boolean(question.printable)}
        onChange={event => onChange(event.target.checked)} />{t`Can print on the member card`}</label>
    <p id={hintId} className="text-xs text-muted">{allowed
      ? t`The card design chooses which marked answers it shows. Multiple choices print joined with commas.`
      : question.sensitive ? t`Sensitive answers never print on a card.`
        : t`Only short text, paragraphs, numbers, dates, choices and yes/no answers can print.`}</p>
  </div>;
}
