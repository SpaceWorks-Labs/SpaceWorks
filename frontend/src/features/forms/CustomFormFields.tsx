import { t } from "@lingui/core/macro";
import { useId, useState } from "react";

import type { CustomAnswers, CustomFormQuestion, CustomFormSchema } from "./customFormTypes";
import { FormV2Fields } from "./FormV2Fields";
import type { Answers, FormSchemaV2, FormState, FieldErrors } from "./types";

type LegacyFieldsProps = Parameters<typeof LegacyCustomFormFields>[0];
type V2FieldsProps = Omit<LegacyFieldsProps, "schema" | "answers" | "onChange" | "errors"> & {
  schema: FormSchemaV2; answers: Answers; onChange: (answers: Answers) => void; errors?: FieldErrors;
  formState?: FormState; onFormStateChange?: (state: FormState) => void;
  renderAsset?: React.ComponentProps<typeof FormV2Fields>["renderAsset"];
  context?: React.ComponentProps<typeof FormV2Fields>["context"];
  uploadFiles?: React.ComponentProps<typeof FormV2Fields>["uploadFiles"];
};
export function CustomFormFields(props: LegacyFieldsProps): React.JSX.Element | null;
export function CustomFormFields(props: V2FieldsProps): React.JSX.Element;
export function CustomFormFields(props: LegacyFieldsProps | V2FieldsProps) {
  if (props.schema && !Array.isArray(props.schema)) return <V2Bridge {...props as V2FieldsProps} />;
  return <LegacyCustomFormFields {...props as LegacyFieldsProps} />;
}
function V2Bridge(props: V2FieldsProps) {
  const [local, setLocal] = useState<FormState>({ answers: props.answers, derivations: {}, save_choices: {}, saved_detail_versions: {} });
  return <fieldset disabled={props.disabled}><FormV2Fields schema={props.schema} errors={props.errors} renderAsset={props.renderAsset} context={props.context} uploadFiles={props.uploadFiles} value={props.formState ?? { ...local, answers: props.answers }} onChange={state => { setLocal(state); props.onChange(state.answers); props.onFormStateChange?.(state); }} /></fieldset>;
}

function LegacyCustomFormFields({ schema, answers, onChange, errors = {}, disabled = false, yesNoAsCheckbox = false }: {
  schema: CustomFormSchema;
  answers: CustomAnswers;
  onChange: (answers: CustomAnswers) => void;
  errors?: Record<string, string>;
  disabled?: boolean;
  yesNoAsCheckbox?: boolean;
}) {
  const prefix = useId();
  if (!schema?.length) return null;

  const setAnswer = (id: string, value: CustomAnswers[string]) => onChange({ ...answers, [id]: value });
  return (
    <fieldset className="grid gap-4" disabled={disabled}>
      <legend className="title-section mb-1">{t`Additional questions`}</legend>
      {schema.map((question) => (
        <QuestionField
          key={question.id}
          question={question}
          inputId={prefix + "-" + question.id}
          value={answers[question.id]}
          error={errors[question.id]}
          yesNoAsCheckbox={yesNoAsCheckbox}
          onChange={(value) => setAnswer(question.id, value)}
        />
      ))}
    </fieldset>
  );
}

function QuestionField({ question, inputId, value, error, yesNoAsCheckbox, onChange }: {
  question: CustomFormQuestion;
  inputId: string;
  value: CustomAnswers[string];
  error?: string;
  yesNoAsCheckbox: boolean;
  onChange: (value: CustomAnswers[string]) => void;
}) {
  const errorId = inputId + "-error";
  const inputProps = {
    id: inputId,
    required: question.required,
    "aria-invalid": Boolean(error),
    "aria-describedby": error ? errorId : undefined,
  };
  const label = <span className="break-words text-sm font-semibold text-ink">{question.label}{question.required ? <span className="text-danger"> *</span> : null}</span>;
  const message = error ? <span id={errorId} className="text-sm font-normal text-danger">{error}</span> : null;

  if (question.type === "yes_no" && yesNoAsCheckbox) {
    return <label className="grid gap-1 text-ink"><span className="flex min-h-11 items-center gap-3 text-sm"><input className="h-5 w-5 shrink-0 accent-brand" id={inputId} type="checkbox" checked={value === true} required={question.required} aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined} onChange={(event) => onChange(event.target.checked)} />{label}</span>{message}</label>;
  }

  if (question.type === "paragraph") {
    return <label className="grid gap-1 text-ink">{label}<textarea {...inputProps} className="desk-input min-h-24 resize-y" maxLength={5000} value={typeof value === "string" ? value : ""} onChange={(event) => onChange(event.target.value)} />{message}</label>;
  }
  if (question.type === "dropdown") {
    return <label className="grid gap-1 text-ink">{label}<select {...inputProps} className="desk-input" value={typeof value === "string" ? value : ""} onChange={(event) => onChange(event.target.value)}><option value="">{t`Select an option`}</option>{question.options.map((option) => <option key={option} value={option}>{option}</option>)}</select>{message}</label>;
  }
  if (question.type === "single_choice" || question.type === "yes_no") {
    const choices: [string, string | boolean][] = question.type === "yes_no"
      ? [["Yes", true], ["No", false]]
      : question.options.map((option) => [option, option]);
    return (
      <fieldset className="grid gap-2" aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined}>
        <legend>{label}</legend>
        <div className="flex flex-wrap gap-x-6 gap-y-1">
          {choices.map(([text, answer]) => <label className="flex min-h-11 min-w-0 items-center gap-3 break-words text-sm text-ink" key={text}><input className="h-5 w-5 shrink-0 accent-brand" type="radio" name={inputId} value={text} checked={value === answer} required={question.required} onChange={() => onChange(answer)} />{text}</label>)}
        </div>
        {message}
      </fieldset>
    );
  }
  if (question.type === "multi_choice") {
    const selected = Array.isArray(value) ? value : [];
    return (
      <fieldset className="grid gap-2" aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined}>
        <legend>{label}</legend>
        <div className="grid gap-x-4 sm:grid-cols-2">
          {question.options.map((option) => <label className="flex min-h-11 min-w-0 items-center gap-3 break-words text-sm text-ink" key={option}><input className="h-5 w-5 shrink-0 accent-brand" type="checkbox" checked={selected.includes(option)} onChange={(event) => onChange(event.target.checked ? [...selected, option] : selected.filter((item) => item !== option))} />{option}</label>)}
        </div>
        {message}
      </fieldset>
    );
  }
  const type = question.type === "number" ? "number" : question.type === "date" ? "date" : "text";
  return <label className="grid gap-1 text-ink">{label}<input {...inputProps} className="desk-input" type={type} maxLength={question.type === "short_text" ? 500 : undefined} value={typeof value === "string" || typeof value === "number" ? value : ""} onChange={(event) => onChange(event.target.value)} />{message}</label>;
}
