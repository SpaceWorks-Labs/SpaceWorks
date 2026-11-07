import { t } from "@lingui/core/macro";
import { useState, type ChangeEvent } from "react";

import { ConfirmDialog } from "../../components/ui";
import { FormBuilderV2 } from "./FormBuilderV2";
import type { FormSchemaV2 } from "./types";

import {
  CHOICE_QUESTION_TYPES,
  CUSTOM_QUESTION_TYPES,
  QUESTION_TYPE_LABELS,
  type CustomFormQuestion,
  type CustomFormSchema,
  type CustomQuestionType,
} from "./customFormTypes";

const QUESTION_TONES = [
  "border-accent bg-accent-soft",
  "border-line bg-accent-soft",
  "border-success bg-success-soft",
  "border-warn bg-warn-soft",
] as const;

function questionTone(id: string) {
  const total = [...id].reduce((sum, character) => sum + character.codePointAt(0)!, 0);
  return QUESTION_TONES[total % QUESTION_TONES.length];
}

function questionId() {
  return "q_" + crypto.randomUUID().replace(/-/g, "_");
}

function newQuestion(): CustomFormQuestion {
  return { id: questionId(), label: "", type: "short_text", options: [], required: false };
}

type LegacyBuilderProps = Parameters<typeof LegacyCustomFormBuilder>[0];
type V2BuilderProps = Omit<LegacyBuilderProps, "value" | "onChange"> & { value: FormSchemaV2; onChange: (schema: FormSchemaV2) => void; context?: React.ComponentProps<typeof FormBuilderV2>["context"] };
export function CustomFormBuilder(props: LegacyBuilderProps): React.JSX.Element;
export function CustomFormBuilder(props: V2BuilderProps): React.JSX.Element;
export function CustomFormBuilder(props: LegacyBuilderProps | V2BuilderProps) {
  if (props.value && !Array.isArray(props.value)) return <fieldset disabled={props.disabled}><FormBuilderV2 value={props.value} context={(props as V2BuilderProps).context} onChange={props.onChange as (schema: FormSchemaV2) => void} /></fieldset>;
  return <LegacyCustomFormBuilder {...props as LegacyBuilderProps} />;
}

function LegacyCustomFormBuilder({
  value,
  onChange,
  disabled = false,
  allowedTypes = CUSTOM_QUESTION_TYPES,
  lockedQuestionIds = [],
  legend = "Custom questions",
  emptyMessage = t`No custom questions. The standard contact fields will still be collected.`,
}: {
  value: CustomFormSchema;
  onChange: (schema: CustomFormSchema) => void;
  disabled?: boolean;
  allowedTypes?: readonly CustomQuestionType[];
  lockedQuestionIds?: readonly string[];
  legend?: string;
  emptyMessage?: string;
}) {
  const questions = value ?? [];
  const replace = (index: number, question: CustomFormQuestion) => {
    onChange(questions.map((item, itemIndex) => itemIndex === index ? question : item));
  };
  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= questions.length) return;
    const next = [...questions];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };

  return (
    <fieldset className="grid gap-3" disabled={disabled}>
      <div>
        <legend className="title-panel">{legend}</legend>
        <p className="eyebrow mt-1">{t`Answers are visible only to authorized staff.`}</p>
      </div>
      {questions.map((question, index) => (
        <QuestionEditor
          key={question.id}
          question={question}
          index={index}
          count={questions.length}
          allowedTypes={allowedTypes}
          locked={lockedQuestionIds.includes(question.id)}
          onChange={(next) => replace(index, next)}
          onMove={(direction) => move(index, direction)}
          onRemove={() => onChange(questions.filter((item) => item.id !== question.id))}
        />
      ))}
      {!questions.length ? (
        <p className="rounded-lg border border-dashed border-outline bg-surface p-3 text-sm text-muted">
          {emptyMessage}
        </p>
      ) : null}
      <button className="desk-button-ghost w-fit" type="button" disabled={questions.length >= 50} onClick={() => onChange([...questions, newQuestion()])}>
        {t`Add question`}</button>
    </fieldset>
  );
}

function QuestionEditor({ question, index, count, allowedTypes, locked, onChange, onMove, onRemove }: {
  question: CustomFormQuestion;
  index: number;
  count: number;
  allowedTypes: readonly CustomQuestionType[];
  locked: boolean;
  onChange: (question: CustomFormQuestion) => void;
  onMove: (direction: -1 | 1) => void;
  onRemove: () => void;
}) {
  const choice = CHOICE_QUESTION_TYPES.has(question.type);
  const [pendingType, setPendingType] = useState<CustomQuestionType | null>(null);
  const applyType = (type: CustomQuestionType) => onChange({
    ...question,
    type,
    options: CHOICE_QUESTION_TYPES.has(type)
      ? (question.options.length ? question.options : [""])
      : [],
  });
  const changeType = (event: ChangeEvent<HTMLSelectElement>) => {
    const type = event.target.value as CustomQuestionType;
    if (choice && !CHOICE_QUESTION_TYPES.has(type) && question.options.length > 0) {
      setPendingType(type);
      return;
    }
    applyType(type);
  };

  return (
    <div className={`rounded-xl border ${questionTone(question.id)} p-3`}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="eyebrow">{t`Question `}<span className="tabular-nums">{index + 1}</span></span>
        <div className="ml-auto flex gap-2">
          <button className="desk-button-ghost" type="button" disabled={index === 0} onClick={() => onMove(-1)} aria-label={"Move question " + (index + 1) + " up"}>{t`Up`}</button>
          <button className="desk-button-ghost" type="button" disabled={index === count - 1} onClick={() => onMove(1)} aria-label={"Move question " + (index + 1) + " down"}>{t`Down`}</button>
          <button className="desk-button-danger" type="button" disabled={locked} onClick={onRemove}>{t`Remove`}</button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_180px]">
        <label className="grid gap-1 text-ink"><span className="eyebrow">{t`Label`}</span>
          <input className="desk-input" required disabled={locked} maxLength={200} value={question.label} onChange={(event) => onChange({ ...question, label: event.target.value })} />
        </label>
        <label className="grid gap-1 text-ink"><span className="eyebrow">{t`Answer type`}</span>
          <select className="desk-input" disabled={locked} value={question.type} onChange={changeType}>
            {allowedTypes.map((type) => <option key={type} value={type}>{QUESTION_TYPE_LABELS[type]}</option>)}
          </select>
        </label>
      </div>
      <label className="mt-3 flex items-center gap-2 text-sm text-ink">
        <input type="checkbox" disabled={locked} checked={question.required} onChange={(event) => onChange({ ...question, required: event.target.checked })} />
        {t`Required question`}</label>
      {choice ? <OptionsEditor question={question} disabled={locked} onChange={onChange} /> : null}
      <ConfirmDialog
        open={pendingType !== null}
        title={t`Change answer type?`}
        message={t`Changing this type will remove its choices. Continue?`}
        confirmLabel={t`Change type`}
        tone="danger"
        onConfirm={() => {
          if (pendingType !== null) applyType(pendingType);
          setPendingType(null);
        }}
        onCancel={() => setPendingType(null)}
      />
    </div>
  );
}

function OptionsEditor({ question, disabled, onChange }: {
  question: CustomFormQuestion;
  disabled: boolean;
  onChange: (question: CustomFormQuestion) => void;
}) {
  return (
    <div className="mt-3 grid gap-2">
      <h3 className="title-section">{t`Choices`}</h3>
      {question.options.map((option, index) => (
        <div className="flex gap-2" key={question.id + "-option-" + index}>
          <input className="desk-input min-w-0 flex-1" aria-label={"Choice " + (index + 1)} required disabled={disabled} maxLength={200} value={option} onChange={(event) => onChange({ ...question, options: question.options.map((item, itemIndex) => itemIndex === index ? event.target.value : item) })} />
          <button className="desk-button-danger" type="button" disabled={disabled || question.options.length === 1} onClick={() => onChange({ ...question, options: question.options.filter((_, itemIndex) => itemIndex !== index) })}>{t`Remove`}</button>
        </div>
      ))}
      <button className="desk-button-ghost w-fit" type="button" disabled={disabled || question.options.length >= 50} onClick={() => onChange({ ...question, options: [...question.options, ""] })}>{t`Add choice`}</button>
    </div>
  );
}
