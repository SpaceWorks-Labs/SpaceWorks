import { FormV2Fields } from "../../forms";
import { CustomFormFields } from "../../forms/CustomFormFields";
import type { CustomFormSchema } from "../../forms/customFormTypes";
import { formSchema, ownerAnswers } from "../programme/formBridge";
import type { Project, ProjectRequirements } from "./types";

export function ProjectFormFields({ requirements, project, change }: { requirements: ProjectRequirements; project: Project; change: (answers: Record<string, unknown>) => void }) {
  return <>{([ ["track", requirements.tracks, project.track_ids], ["prize", requirements.prizes, project.prize_ids] ] as const).flatMap(([kind, rows, selected]) => rows.filter(row => selected.includes(row.id)).map(row => {
    if (!row.form || Array.isArray(row.form) && !row.form.length || typeof row.form === "object" && !Object.keys(row.form).length) return null;
    const key = `${kind}:${row.id}`;
    const value = project.form_answers[key];
    const store = (answers: Record<string, unknown>) => change({ ...project.form_answers, [key]: answers });
    const legacy = value && typeof value === "object" && "answers" in value && Array.isArray(value.answers)
      ? Object.fromEntries(value.answers.filter((answer: Record<string, unknown>) => typeof answer.id === "string" && "value" in answer).map((answer: Record<string, unknown>) => [answer.id, answer.value])) : value ?? {};
    if (Array.isArray(row.form)) return <fieldset key={key} className="grid gap-3"><legend className="font-semibold">{row.label}</legend><CustomFormFields schema={row.form as CustomFormSchema} answers={legacy as Record<string, string>} onChange={store} /></fieldset>;
    const schema = formSchema(row.form);
    return <fieldset key={key} className="grid gap-3"><legend className="font-semibold">{row.label}</legend><FormV2Fields schema={schema} allowSavedDetails={false}
      value={{ answers: ownerAnswers(value, schema), derivations: {}, save_choices: {}, saved_detail_versions: {} }} onChange={state => store(state.answers)} /></fieldset>;
  }))}</>;
}
