import { t } from "@lingui/core/macro";

import type { MachineType } from "../../../machinesApi";
import type { Prefill, TemplateSpec } from "./templatesApi";

export const WIZARD_STEPS = ["template", "basics", "consumables", "intake", "pricing", "access", "bookings", "safety", "maintenance", "notifications", "documents", "machines"] as const;
export type WizardStep = typeof WIZARD_STEPS[number];

export const stepLabels = (): Record<WizardStep, string> => ({
  template: t`Template`, basics: t`Basics`, consumables: t`Consumables`, intake: t`Job and intake fields`, pricing: t`Pricing`, access: t`Access`,
  bookings: t`Bookings`, safety: t`Safety`, maintenance: t`Maintenance`, notifications: t`Notifications`, documents: t`Documents and training`, machines: t`Add machines`,
});

/** What every step may read: the host, the type once it exists, and what the chosen template pre-filled. */
export type WizardContext = {
  makerspaceId: number;
  machineType: MachineType | null;
  spec: TemplateSpec | null;
  prefill: Prefill | null;
  enabledFeatures: string[];
  machineServiceEnabled: boolean;
  printerAdapter: boolean;
  /** Screen links for the settings a step points at instead of re-implementing. */
  hrefFor: (tab: string) => string;
  /** New machines are shown on the public site (the Basics "public visibility" choice). */
  publicMachines: boolean;
};

export type StepProps = { ctx: WizardContext };
