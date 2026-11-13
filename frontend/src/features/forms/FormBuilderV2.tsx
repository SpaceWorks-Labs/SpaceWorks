import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ArrowDown, ArrowUp, Heading, Plus, Trash2 } from "lucide-react";
import { Card } from "../../components/ui";
import { QuestionEditor } from "./QuestionEditor";
import { SectionHeadingEditor } from "./SectionHeadingEditor";
import { MAX_SECTIONS, newSection, nextSectionAnchor, withoutQuestion } from "./sections";
import { questionTypeLabel } from "./questionLabels";
import { FILE_PURPOSES, TRAVEL_MODES, QUESTION_TYPES, type FormContext, type FormSchemaV2, type FormSection, type QuestionType } from "./types";

/** `memberCard`: a membership join form, whose plain answers may print on the member card (parity O-B4). */
export function FormBuilderV2({ value, onChange, errors = {}, context, memberCard = false }: { value: FormSchemaV2; onChange: (value: FormSchemaV2) => void; errors?: Record<string, string>; context?: FormContext; memberCard?: boolean }) {
  const [type, setType] = useState<QuestionType>("short_text");
  const [announcement, setAnnouncement] = useState("");
  const available = QUESTION_TYPES.filter(item => (context !== "stage" || !["date_of_birth", "age_at_event"].includes(item)) && (item !== "file" || context));
  const selectedType = available.includes(type) ? type : "short_text";
  const sections = value.sections ?? [];
  const setSections = (next: FormSection[]) => onChange({ ...value, sections: next });
  const anchor = nextSectionAnchor(value);
  const move = (index: number, direction: number) => {
    const questions = [...value.questions];
    [questions[index], questions[index + direction]] = [questions[index + direction], questions[index]];
    onChange({ ...value, questions }); setAnnouncement(`Moved question to position ${index + direction + 1}. Validate conditions before saving.`);
  };
  return <section className="grid gap-4" aria-label={t`Form builder`}><p role="status" className="sr-only">{announcement}</p>
    <p className="text-sm text-muted">{t`Conditions can refer only to earlier questions. Saving a new revision preserves answers already locked to an earlier revision.`}</p>
    {value.questions.map((question, index) => <div key={question.id} className="grid gap-3">
      {sections.filter(section => section.before === question.id).map(section => <SectionHeadingEditor key={section.id} section={section} questions={value.questions}
        onChange={next => setSections(sections.map(item => item.id === next.id ? next : item))}
        onRemove={() => { setSections(sections.filter(item => item.id !== section.id)); setAnnouncement(t`Heading removed.`); }} />)}
      <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><h3 className="title-section">{t`Question ${index + 1} · ${questionTypeLabel(question.type)}`}</h3><div className="flex gap-2">
        <button className="desk-button" type="button" aria-label={t`Move ${question.label} up`} disabled={index === 0} onClick={() => move(index, -1)}><ArrowUp size={20} aria-hidden="true" /></button>
        <button className="desk-button" type="button" aria-label={t`Move ${question.label} down`} disabled={index === value.questions.length - 1} onClick={() => move(index, 1)}><ArrowDown size={20} aria-hidden="true" /></button>
        <button className="desk-button-danger-outline" type="button" aria-label={t`Delete ${question.label}`} onClick={() => onChange(withoutQuestion(value, question.id))}><Trash2 size={20} aria-hidden="true" /></button>
      </div></div>
      <QuestionEditor context={context} memberCard={memberCard} question={question} earlier={value.questions.slice(0, index)} onChange={q => onChange({ ...value, questions: value.questions.map(item => item.id === q.id ? q : item) })} />
      {errors[question.id] ? <p role="alert" className="mt-2 text-sm text-danger">{errors[question.id]}</p> : null}
    </Card></div>)}
    <div className="flex flex-wrap items-end gap-3"><label className="grid gap-1 text-sm">{t`Question type`}<select className="desk-input" value={selectedType} onChange={e => setType(e.target.value as QuestionType)}>{available.map(item => <option key={item} value={item}>{questionTypeLabel(item)}</option>)}</select></label>
      <button className="desk-button" type="button" disabled={value.questions.length >= 50} onClick={() => {
        const financeFile = selectedType === "file" && context !== "stage";
        onChange({ ...value, questions: [...value.questions, { id: `q-${crypto.randomUUID()}`, type: selectedType, label: t`New question`, required: false,
          sensitive: financeFile, disclosure: { organizer: !financeFile, reviewer: false, judge: false },
          ...(selectedType === "money" ? { money: { currencies: ["INR"], min_minor: 0, max_minor: 10000000 } } : {}),
          ...(selectedType === "file" && context ? { file: { purpose: FILE_PURPOSES[context], max_files: 1, max_bytes_each: 10485760 } } : {}),
          ...(selectedType === "itinerary" ? { itinerary: { modes: [...TRAVEL_MODES] } } : {}),
          ...(["single_choice", "multi_choice"].includes(selectedType) ? { options: [{ id: "first", label: t`First choice` }] } : {}) }] });
      }}><Plus size={20} aria-hidden="true" />{t`Add question`}</button>
      <button className="desk-button" type="button" disabled={!anchor || sections.length >= MAX_SECTIONS} onClick={() => {
        if (!anchor) return;
        setSections([...sections, newSection(anchor, t`New section`)]); setAnnouncement(t`Heading added. Choose the question it sits above.`);
      }}><Heading size={20} aria-hidden="true" />{t`Add section heading`}</button></div>
    {!anchor ? <p className="text-sm text-muted">{t`Add a question first; a section heading sits above a question.`}</p> : null}
  </section>;
}
