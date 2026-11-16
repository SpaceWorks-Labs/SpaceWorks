import { t } from "@lingui/core/macro";
import { readStorage, writeStorage } from "../../../lib/safeStorage";
import type { SetupState } from "../setupChecklistState";

/**
 * The guided first-run setup for a Space Manager (decision 235). Each step is skippable.
 * Where the server can tell whether a step is done (logo, hours, areas, staff) the wizard
 * reads that from the setup-state endpoint; the browser only remembers where you stopped.
 */
export type WizardStepKey = "name" | "logo" | "hours" | "areas" | "staff";
export type WizardProgress = { step: number; finished: boolean; started: boolean };

export const WIZARD_STEPS: readonly WizardStepKey[] = ["name", "logo", "hours", "areas", "staff"];

export function wizardStepTitle(step: WizardStepKey) {
  switch (step) {
    case "name": return t`Name your space`;
    case "logo": return t`Add your logo`;
    case "hours": return t`Set your opening hours`;
    case "areas": return t`Choose what your space runs`;
    case "staff": return t`Invite your staff`;
  }
}

export function wizardStepHint(step: WizardStepKey) {
  switch (step) {
    case "name": return t`This name appears on your public pages, emails and receipts.`;
    case "logo": return t`Your logo appears on public pages. Without one, the name is used instead.`;
    case "hours": return t`Members see when you are open. Bookings and loan due dates follow these hours.`;
    case "areas": return t`Switch on only what you use. Anything switched off stays hidden, and its data is kept.`;
    case "staff": return t`Each person gets an email and signs in with their own account.`;
  }
}

/** Server-derived completion; the name step has no server signal, so it counts once saved. */
export function wizardStepDone(step: WizardStepKey, state: SetupState | undefined) {
  if (!state) return false;
  switch (step) {
    case "name": return false;
    case "logo": return state.logo_set === true;
    case "hours": return state.hours_set;
    case "areas": return state.modules_chosen;
    case "staff": return state.staff_invited;
  }
}

/** True when nothing has been set up yet: the wizard then opens by itself once. */
export function nothingSetUp(state: SetupState) {
  return !state.logo_set && !state.hours_set && !state.modules_chosen && !state.staff_invited;
}

const storageKey = (owner: string, space: number) => `spaceworks.setup.wizard:${owner}:${space}`;

export function readWizardProgress(owner: string, space: number): WizardProgress {
  try {
    const raw = JSON.parse(readStorage(storageKey(owner, space), "{}")) as Partial<WizardProgress>;
    const step = Number.isInteger(raw.step) ? Math.min(Math.max(raw.step as number, 0), WIZARD_STEPS.length - 1) : 0;
    return { step, finished: raw.finished === true, started: raw.started === true };
  } catch {
    return { step: 0, finished: false, started: false };
  }
}

export function writeWizardProgress(owner: string, space: number, progress: WizardProgress) {
  writeStorage(storageKey(owner, space), JSON.stringify(progress));
}
