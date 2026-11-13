import { t } from "@lingui/core/macro";
import { Heading, Trash2 } from "lucide-react";

import type { FormSection, Question } from "./types";

/**
 * One section heading in the v2 form builder (parity O-B2). A heading has no answer: it only sits
 * above a question, so its one structural choice is which question that is. Members see it only
 * while at least one question beneath it (up to the next heading) is visible.
 */
export function SectionHeadingEditor({ section, questions, onChange, onRemove }: {
  section: FormSection; questions: Question[]; onChange: (section: FormSection) => void; onRemove: () => void;
}) {
  const update = (patch: Partial<FormSection>) => onChange({ ...section, ...patch });
  const name = section.heading.trim() || t`Untitled heading`;
  return <div role="group" aria-label={t`Section heading: ${name}`}
    className="grid gap-3 rounded-xl border border-dashed border-outline bg-surface p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="flex items-center gap-2 text-sm font-semibold text-ink"><Heading size={18} aria-hidden="true" />{t`Section heading`}</p>
      <button className="desk-button-danger-outline" type="button" aria-label={t`Remove heading ${name}`} onClick={onRemove}>
        <Trash2 size={20} aria-hidden="true" /></button>
    </div>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="grid gap-1 text-sm">{t`Heading`}
        <input className="desk-input" required maxLength={120} value={section.heading} onChange={event => update({ heading: event.target.value })} />
      </label>
      <label className="grid gap-1 text-sm">{t`Shown above`}
        <select className="desk-input max-w-full" value={section.before} onChange={event => update({ before: event.target.value })}>
          {questions.map((question, index) => <option key={question.id} value={question.id}>{t`Question ${index + 1}: ${question.label}`}</option>)}
        </select>
      </label>
    </div>
    <label className="grid gap-1 text-sm">{t`Help text (optional)`}
      <textarea className="desk-input min-h-16" maxLength={1000} value={section.help ?? ""}
        onChange={event => update({ help: event.target.value || undefined })} />
    </label>
  </div>;
}
