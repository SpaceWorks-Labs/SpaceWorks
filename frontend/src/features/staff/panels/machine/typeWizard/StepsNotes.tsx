import { t } from "@lingui/core/macro";

import { JobSettingsEditor } from "../JobSettingsEditor";
import { IntakeFieldsEditor } from "./IntakeFieldsEditor";
import { ReadOnlyStep } from "./ReadOnlyStep";
import type { StepProps } from "./wizardTypes";

/** Step 4: the questions members answer (existing intake endpoint) and the job settings (existing job-settings endpoint). */
export function StepIntake({ ctx }: StepProps) {
  const type = ctx.machineType!;
  const custom = type.makerspace !== null;
  const fields = ctx.spec?.intake_fields ?? [];
  return <div className="grid gap-4">
    {custom && ctx.enabledFeatures.includes("machines.structured_intake") ? <IntakeFieldsEditor makerspaceId={ctx.makerspaceId} typeId={type.id} /> :
      <ReadOnlyStep intro={custom ? t`Structured machine intake is switched off in features, so these questions are notes only.` : t`Built-in types keep their own intake, so these questions are notes only.`}
        rows={fields.map(field => [field.label, `${field.type}${field.required ? `, ${t`required`}` : ""}`])} />}
    {ctx.machineServiceEnabled ? <JobSettingsEditor makerspaceId={ctx.makerspaceId} machineTypeId={type.id} /> :
      <p className="text-sm text-muted">{t`Job requests need the machine service module, which is off here.`}</p>}
  </div>;
}
