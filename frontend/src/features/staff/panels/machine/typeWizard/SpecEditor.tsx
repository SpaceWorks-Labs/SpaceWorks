import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";

import { SpecConsumables } from "./SpecConsumables";
import { SpecIntake } from "./SpecIntake";
import { SpecMaintenance } from "./SpecMaintenance";
import { SpecAccess, SpecBasics, SpecBookings, SpecDocuments, SpecJob, SpecNotifications, SpecPricing, SpecSafety } from "./SpecSections";
import type { SpecProblems, SpecSection } from "./specValidate";
import type { TemplateSpec } from "./templatesApi";

const TITLES = (): Record<SpecSection, string> => ({ basics: t`Basics`, consumables: t`Consumables`, intake_fields: t`Intake fields`, pricing: t`Pricing`, access: t`Access`,
  bookings: t`Bookings`, safety: t`Safety`, maintenance: t`Maintenance`, job: t`Jobs`, notifications: t`Notifications`, documents: t`Documents and training` });

function Section({ id, problem, server, children }: { id: SpecSection; problem?: string; server?: string; children: ReactNode }) {
  const shown = problem || server;
  return <details className="rounded-lg border border-line" open={Boolean(shown) || undefined}>
    <summary className="min-h-11 cursor-pointer px-3 py-2 text-sm font-semibold text-ink">{TITLES()[id]}{shown ? <span className="ml-2 text-danger">{t`Needs attention`}</span> : null}</summary>
    <div className="grid gap-3 p-3">{children}
      {problem ? <p role="alert" className="text-sm text-danger">{problem}</p> : null}
      {server ? <p role="alert" className="text-sm text-danger">{server}</p> : null}</div>
  </details>;
}

/** A template's spec as one form per section, never raw JSON. `problems` are the client limits; a server refusal is shown under the section it names. */
export function SpecEditor({ spec, onChange, problems, serverSection, serverText }: {
  spec: TemplateSpec; onChange: (next: TemplateSpec) => void; problems: SpecProblems; serverSection: SpecSection | null; serverText?: string;
}) {
  const set = <K extends keyof TemplateSpec>(key: K, value: TemplateSpec[K]) => onChange({ ...spec, [key]: value });
  const section = (id: SpecSection, children: ReactNode) => <Section id={id} problem={problems[id]} server={serverSection === id ? serverText : undefined}>{children}</Section>;
  return <div className="grid gap-2" aria-label={t`Template settings`}>
    {section("basics", <SpecBasics value={spec.basics} onChange={value => set("basics", value)} />)}
    {section("consumables", <SpecConsumables rows={spec.consumables} onChange={value => set("consumables", value)} />)}
    {section("intake_fields", <SpecIntake fields={spec.intake_fields} onChange={value => set("intake_fields", value)} />)}
    {section("pricing", <SpecPricing value={spec.pricing} onChange={value => set("pricing", value)} />)}
    {section("access", <SpecAccess value={spec.access} onChange={value => set("access", value)} />)}
    {section("bookings", <SpecBookings value={spec.bookings} onChange={value => set("bookings", value)} />)}
    {section("safety", <SpecSafety value={spec.safety} onChange={value => set("safety", value)} />)}
    {section("maintenance", <SpecMaintenance items={spec.maintenance} onChange={value => set("maintenance", value)} />)}
    {section("job", <SpecJob value={spec.job} onChange={value => set("job", value)} />)}
    {section("notifications", <SpecNotifications value={spec.notifications} onChange={value => set("notifications", value)} />)}
    {section("documents", <SpecDocuments value={spec.documents} onChange={value => set("documents", value)} />)}
  </div>;
}
