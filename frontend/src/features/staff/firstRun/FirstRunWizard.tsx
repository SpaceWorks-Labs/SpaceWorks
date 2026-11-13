import { t } from "@lingui/core/macro";
import { Suspense, useState } from "react";
import { Modal, ProgressBar, StatusPill } from "../../../components/ui";
import type { Makerspace } from "../panels/shared";
import type { SetupState } from "../setupChecklistState";
import { ModulesPanel } from "../StaffTabLoaders";
import { HoursStep, LogoStep, NameStep, StaffStep } from "./FirstRunSteps";
import {
  WIZARD_STEPS, readWizardProgress, wizardStepDone, wizardStepHint, wizardStepTitle, writeWizardProgress,
  type WizardStepKey,
} from "./firstRunWizardState";
import { LogoLoader } from "../../../components/LogoLoader";

/** Steps whose primary button saves the step's form before moving on. */
const SAVES: readonly WizardStepKey[] = ["name", "hours"];

/**
 * Guided first-run setup (decision 235): name, logo, hours, areas, staff. Every step can be
 * skipped; closing keeps your place, and reopening resumes at the same step.
 */
export function FirstRunWizard({ makerspace, owner, state, onClose }: {
  makerspace: Makerspace; owner: string; state: SetupState | undefined; onClose: () => void;
}) {
  const [step, setStep] = useState(() => readWizardProgress(owner, makerspace.id).step);
  const key = WIZARD_STEPS[step];
  const last = step === WIZARD_STEPS.length - 1;
  const go = (next: number) => {
    const finished = next >= WIZARD_STEPS.length;
    writeWizardProgress(owner, makerspace.id, { step: finished ? step : next, finished, started: true });
    if (finished) onClose(); else setStep(next);
  };
  const done = wizardStepDone(key, state);
  const footer = <div className="flex flex-wrap items-center justify-between gap-2">
    <button type="button" className="desk-button-ghost" disabled={step === 0} onClick={() => go(step - 1)}>{t`Back`}</button>
    <div className="flex flex-wrap gap-2">
      {!last ? <button type="button" className="desk-button" onClick={() => go(step + 1)}>{t`Skip for now`}</button> : null}
      {SAVES.includes(key)
        ? <button type="submit" form="first-run-step" className="desk-button-primary">{t`Save and continue`}</button>
        : <button type="button" className="desk-button-primary" onClick={() => go(step + 1)}>{last ? t`Finish` : t`Continue`}</button>}
    </div>
  </div>;
  return <Modal open size="xl" title={t`Set up ${makerspace.name}`} footer={footer} onClose={() => {
    writeWizardProgress(owner, makerspace.id, { step, finished: false, started: true });
    onClose();
  }}>
    <div className="grid gap-4">
      <ProgressBar label={t`Step ${step + 1} of ${WIZARD_STEPS.length}`} value={(step + 1) / WIZARD_STEPS.length} />
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold text-ink">{wizardStepTitle(key)}</h3>
        {done ? <StatusPill tone="success" label={t`Done`} /> : null}
      </div>
      <p className="text-sm text-muted">{wizardStepHint(key)}</p>
      {key === "name" ? <NameStep makerspace={makerspace} onSaved={() => go(step + 1)} /> : null}
      {key === "logo" ? <LogoStep makerspace={makerspace} onSaved={() => go(step + 1)} /> : null}
      {key === "hours" ? <HoursStep makerspace={makerspace} onSaved={() => go(step + 1)} /> : null}
      {key === "areas" ? <Suspense fallback={<LogoLoader label={t`Loading areas…`} size={48} className="min-h-16 py-3" />}><ModulesPanel makerspaceId={makerspace.id} /></Suspense> : null}
      {key === "staff" ? <StaffStep makerspace={makerspace} onSaved={() => go(step + 1)} /> : null}
    </div>
  </Modal>;
}
