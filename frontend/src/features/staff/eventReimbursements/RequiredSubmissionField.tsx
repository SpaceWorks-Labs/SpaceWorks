import { t } from "@lingui/core/macro";
import { Field } from "../../../components/ui/Field";
import type { PolicySettings, RequiredSubmission } from "./types";

const MODES: Record<RequiredSubmission, string> = {
  none: "No submission needed", any_stage: "Any submitted stage", stage: "A chosen stage", final_stage: "The final stage",
  shortlisted_at: "Shortlisted at a chosen stage", finalist: "A published finalist",
};

/** G11 (#180): which submission earns travel support. `require_project_submission` stays its yes/no mirror. */
export function RequiredSubmissionField({ value, onChange }: { value: PolicySettings; onChange: (value: PolicySettings) => void }) {
  const mode: RequiredSubmission = value.required_submission ?? (value.require_project_submission ? "any_stage" : "none");
  const needsStage = mode === "stage" || mode === "shortlisted_at";
  const set = (next: RequiredSubmission, stage: number | null) => onChange({ ...value, required_submission: next,
    required_submission_stage: next === "stage" || next === "shortlisted_at" ? stage ?? 1 : null, require_project_submission: next !== "none" });
  return <div className="grid gap-4 md:grid-cols-2">
    <Field label={t`Project submission required`}><select className="desk-input" value={mode} onChange={e => set(e.target.value as RequiredSubmission, value.required_submission_stage ?? null)}>
      {Object.entries(MODES).map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></Field>
    {needsStage ? <Field label={t`Stage position`} hint={mode === "shortlisted_at" ? t`A stage that ends with a shortlist.` : t`1 is the first stage.`}>
      <input className="desk-input" type="number" min={1} max={50} required value={value.required_submission_stage ?? 1}
        onChange={e => set(mode, e.target.valueAsNumber || 1)} /></Field> : null}
  </div>;
}
