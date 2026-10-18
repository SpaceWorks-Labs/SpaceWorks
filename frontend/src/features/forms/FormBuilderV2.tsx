import { useState } from "react";
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { Card } from "../../components/ui";
import { QuestionEditor } from "./QuestionEditor";
import { FILE_PURPOSES, TRAVEL_MODES, QUESTION_TYPES, type FormContext, type FormSchemaV2, type QuestionType } from "./types";

export function FormBuilderV2({ value, onChange, errors = {}, context }: { value: FormSchemaV2; onChange: (value: FormSchemaV2) => void; errors?: Record<string, string>; context?: FormContext }) {
  const [type, setType] = useState<QuestionType>("short_text");
  const [announcement, setAnnouncement] = useState("");
  const available = QUESTION_TYPES.filter(item => (context !== "stage" || !["date_of_birth", "age_at_event"].includes(item)) && (item !== "file" || context));
  const selectedType = available.includes(type) ? type : "short_text";
  const move = (index: number, direction: number) => {
    const questions = [...value.questions];
    [questions[index], questions[index + direction]] = [questions[index + direction], questions[index]];
    onChange({ ...value, questions }); setAnnouncement(`Moved question to position ${index + direction + 1}. Validate conditions before saving.`);
  };
  return <section className="grid gap-4" aria-label="Form builder"><p role="status" className="sr-only">{announcement}</p>
    <p className="text-sm text-muted">Conditions can refer only to earlier questions. Saving a new revision preserves answers already locked to an earlier revision.</p>
    {value.questions.map((question, index) => <Card key={question.id}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><h3 className="title-section">Question {index + 1} · {question.type.replace(/_/g, " ")}</h3><div className="flex gap-2">
        <button className="desk-button" type="button" aria-label={`Move ${question.label} up`} disabled={index === 0} onClick={() => move(index, -1)}><ArrowUp size={20} aria-hidden="true" /></button>
        <button className="desk-button" type="button" aria-label={`Move ${question.label} down`} disabled={index === value.questions.length - 1} onClick={() => move(index, 1)}><ArrowDown size={20} aria-hidden="true" /></button>
        <button className="desk-button-danger-outline" type="button" aria-label={`Delete ${question.label}`} onClick={() => onChange({ ...value, questions: value.questions.filter(q => q.id !== question.id) })}><Trash2 size={20} aria-hidden="true" /></button>
      </div></div>
      <QuestionEditor context={context} question={question} earlier={value.questions.slice(0, index)} onChange={q => onChange({ ...value, questions: value.questions.map(item => item.id === q.id ? q : item) })} />
      {errors[question.id] ? <p role="alert" className="mt-2 text-sm text-danger">{errors[question.id]}</p> : null}
    </Card>)}
    <div className="flex flex-wrap items-end gap-3"><label className="grid gap-1 text-sm">Question type<select className="desk-input" value={selectedType} onChange={e => setType(e.target.value as QuestionType)}>{available.map(item => <option key={item} value={item}>{item.replace(/_/g, " ")}</option>)}</select></label>
      <button className="desk-button" type="button" disabled={value.questions.length >= 50} onClick={() => {
        const financeFile = selectedType === "file" && context !== "stage";
        onChange({ ...value, questions: [...value.questions, { id: `q-${crypto.randomUUID()}`, type: selectedType, label: "New question", required: false,
          sensitive: financeFile, disclosure: { organizer: !financeFile, reviewer: false, judge: false },
          ...(selectedType === "money" ? { money: { currencies: ["INR"], min_minor: 0, max_minor: 10000000 } } : {}),
          ...(selectedType === "file" && context ? { file: { purpose: FILE_PURPOSES[context], max_files: 1, max_bytes_each: 10485760 } } : {}),
          ...(selectedType === "itinerary" ? { itinerary: { modes: [...TRAVEL_MODES] } } : {}),
          ...(["single_choice", "multi_choice"].includes(selectedType) ? { options: [{ id: "first", label: "First choice" }] } : {}) }] });
      }}><Plus size={20} aria-hidden="true" />Add question</button></div>
  </section>;
}
