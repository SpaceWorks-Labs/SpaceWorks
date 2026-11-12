import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";

import type { WizardContext } from "../wizardTypes";

export const type = { id: 9, slug: "laser-cutter", name: "Laser cutter", icon: "zap", is_builtin: false, managing_action: "", makerspace: 1, capability_config: { metering_unit: "minutes", requires_booking: false } };
export const baseSpec = { version: 1, basics: { metering_unit: "minutes", requires_booking: false, is_public: true }, consumables: [{ key: "acrylic_sheet", name: "Acrylic sheet", kind: "material", unit: "sheet", required: true, estimate_by: "member", record_by: ["staff"], attributes: {} }],
  intake_fields: [], pricing: { charge_by: "time" }, access: { open_to_all_members: false, supervised: true }, bookings: { bookable: true }, safety: {},
  maintenance: [{ title: "Clean the lens", trigger: "days", interval: 14 }], job: { accepts_job_requests: true, runs_unattended: false },
  notifications: { job_finished: true, job_failed: false, low_stock: true }, documents: { training_notes: "Wear eye protection." } };

export const context = (patch: Partial<WizardContext> = {}): WizardContext => ({ makerspaceId: 1, machineType: type as never, spec: baseSpec as never, prefill: null,
  enabledFeatures: [], machineServiceEnabled: true, printerAdapter: false, hrefFor: () => "#", publicMachines: false, ...patch });

export const renderWithQuery = (ui: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>);
