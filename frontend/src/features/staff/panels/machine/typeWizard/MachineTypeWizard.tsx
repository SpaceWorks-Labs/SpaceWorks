import { t } from "@lingui/core/macro";
import { useState } from "react";

import { BoxArt } from "../../../../../components/BoxSpinner";
import { Modal } from "../../../../../components/ui";
import type { MachineType } from "../../../machinesApi";
import { ConsumableProfileEditor } from "./ConsumableProfileEditor";
import { StepAccess } from "./StepAccess";
import { StepBookings } from "./StepBookings";
import { StepDocuments } from "./StepDocuments";
import { StepBasics } from "./StepBasics";
import { StepMachines } from "./StepMachines";
import { StepMaintenance } from "./StepMaintenance";
import { StepNotifications } from "./StepNotifications";
import { StepPricing } from "./StepPricing";
import { StepSafety } from "./StepSafety";
import { BLANK, StepTemplate } from "./StepTemplate";
import { StepIntake } from "./StepsNotes";
import { useApplyTemplate, type ApplyResult, type TypeTemplate } from "./templatesApi";
import { WIZARD_STEPS, stepLabels, type WizardContext, type WizardStep } from "./wizardTypes";

type Props = {
  makerspaceId: number; machineType?: MachineType | null; onClose: () => void; enabledFeatures?: string[];
  machineServiceEnabled?: boolean; printerAdapter?: boolean; hrefFor?: (tab: string) => string;
};

/** "Add a machine type": a step-by-step setup for any machine. Opened on an existing type it is the same editor, every step editable later. */
export function MachineTypeWizard({ makerspaceId, machineType: existing = null, onClose, enabledFeatures = [], machineServiceEnabled = false, printerAdapter = false, hrefFor = () => "#" }: Props) {
  const [type, setType] = useState<MachineType | null>(existing);
  const [step, setStep] = useState<WizardStep>(existing ? "basics" : "template");
  const [template, setTemplate] = useState<TypeTemplate | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [applied, setApplied] = useState<ApplyResult | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [publicMachines, setPublicMachines] = useState(false);
  const apply = useApplyTemplate(makerspaceId);
  const labels = stepLabels();
  const index = WIZARD_STEPS.indexOf(step);
  const reachable = (key: WizardStep) => key === "template" || (key === "basics" ? picked !== null || type !== null : type !== null);
  const ctx: WizardContext = { makerspaceId, machineType: type, spec: template?.spec ?? null, prefill: applied?.prefill ?? null, enabledFeatures, machineServiceEnabled,
    printerAdapter, hrefFor, publicMachines };
  const pick = (row: TypeTemplate | null) => { setPicked(row?.key ?? BLANK); setTemplate(row); setPublicMachines(row?.spec.basics.is_public ?? false); };
  const applyToExisting = () => { if (type && template) apply.mutate({ key: template.key, body: { machine_type_id: type.id } }, { onSuccess: setApplied }); };
  const next = WIZARD_STEPS[index + 1];
  const blocked = !next || !reachable(next);
  const body = {
    template: <><StepTemplate makerspaceId={makerspaceId} selected={picked} onSelect={pick} existing={type !== null} applying={apply.isPending} error={apply.error?.message} />
      {type ? <div className="mt-3 grid gap-2"><div><button type="button" className="desk-button-primary min-h-11" disabled={!template || apply.isPending} onClick={applyToExisting}>
        {apply.isPending ? <><BoxArt size={16} mono />{t`Applying…`}</> : t`Apply template to this type`}</button></div>
      {applied ? <p role="status" className="text-sm text-success-ink">{t`Added ${applied.consumables_added.length}, kept ${applied.consumables_skipped.length} that already existed.`}</p> : null}</div> : null}</>,
    basics: <StepBasics key={type?.id ?? "new"} makerspaceId={makerspaceId} machineType={type} template={template} machineServiceEnabled={machineServiceEnabled}
      publicMachines={publicMachines} onPublicChange={setPublicMachines}
      onSaved={(saved, result, note) => { setType(saved); if (result) setApplied(result); setWarning(note); if (!type) setStep("consumables"); }} />,
    consumables: type ? <ConsumableProfileEditor makerspaceId={makerspaceId} typeId={type.id} /> : null,
    intake: <StepIntake ctx={ctx} />, pricing: <StepPricing ctx={ctx} />, access: <StepAccess ctx={ctx} />, bookings: <StepBookings ctx={ctx} />,
    safety: <StepSafety ctx={ctx} />, maintenance: <StepMaintenance ctx={ctx} />, notifications: <StepNotifications ctx={ctx} />,
    documents: <StepDocuments ctx={ctx} />, machines: type ? <StepMachines ctx={ctx} /> : null,
  } satisfies Record<WizardStep, React.ReactNode>;
  return <Modal open size="xl" title={type ? t`Set up ${type.name}` : t`Add a machine type`} onClose={onClose}
    footer={<div className="flex w-full flex-wrap justify-between gap-2">
      <button type="button" className="desk-button-ghost min-h-11" disabled={index === 0} onClick={() => setStep(WIZARD_STEPS[index - 1])}>{t`Back`}</button>
      <span className="flex gap-2"><button type="button" className="desk-button-ghost min-h-11" onClick={onClose}>{t`Close`}</button>
        {next ? <button type="button" className="desk-button-primary min-h-11" disabled={blocked} onClick={() => setStep(next)}>{t`Next: ${labels[next]}`}</button> : <button type="button" className="desk-button-primary min-h-11" onClick={onClose}>{t`Done`}</button>}</span></div>}>
    <div className="grid gap-4">
      <div className="grid gap-2">
        <p className="eyebrow" aria-live="polite">{t`Step ${index + 1} of ${WIZARD_STEPS.length}`}</p>
        <progress className="h-2 w-full" max={WIZARD_STEPS.length} value={index + 1} aria-hidden="true" />
        <label className="grid gap-1 text-sm">{t`Go to step`}<select className="desk-input" value={step} onChange={event => setStep(event.target.value as WizardStep)}>
          {WIZARD_STEPS.map((key, position) => <option key={key} value={key} disabled={!reachable(key)}>{`${position + 1}. ${labels[key]}`}</option>)}</select></label>
      </div>
      <h3 className="title-panel">{labels[step]}</h3>
      {warning ? <p role="status" className="rounded-md border border-line bg-surface p-3 text-sm">{t`The type was created, but its job defaults could not be saved: ${warning}. Set them in the Job and intake step.`}</p> : null}
      {body[step]}
    </div>
  </Modal>;
}
