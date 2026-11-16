import { t } from "@lingui/core/macro";
import { useEffect, useState, type ReactNode } from "react";
import { FlowLayout } from "../../../../components/layouts/FlowLayout";
import { hoursDraft, validateHours } from "../../makerspaceProfileForm";
import { CreationWizardSteps } from "./CreationWizardSteps";
import { OrganizationPicker, organizationFieldErrors } from "./OrganizationPicker";
import type { MakerspaceForm } from "./types";
import { SpaceKindChooser } from "./SpaceKindChooser";
import { spaceNounTitle } from "../../../../lib/spaceNoun";

const steps = ["Identity", "Profile and hours", "Modules and pack", "First staff", "Review"];
export function CreateMakerspaceModal({ open, form, pending, error, onChange, onClose, onSubmit, identityExtra }: {
  open: boolean; form: MakerspaceForm; pending: boolean; error: unknown;
  onChange: (form: MakerspaceForm) => void; onClose: () => void; onSubmit: () => void;
  /** Extra fields on the Identity step (the platform console adds the hosting type, decision 236). */
  identityExtra?: ReactNode;
}) {
  const [step, setStep] = useState(0);
  const organization = form.kind === "organization";
  const nounTitle = spaceNounTitle(form.kind ?? "makerspace");
  const title = organization ? t`Create organization workspace` : t`Create makerspace`;
  const [invalid, setInvalid] = useState<string | null>(null);
  const organizationChosen = Boolean(form.organization && (form.organization !== "new" || (form.organization_name ?? form.name).trim()));
  useEffect(() => { if (open) { setStep(0); setInvalid(null); } }, [open]);
  useEffect(() => {
    const errors = organizationFieldErrors(error);
    if (errors.organization_id || errors.organization_name) setStep(0);
  }, [error]);
  const validate = () => {
    if (!form.name.trim() || !/^[A-Z0-9]{4}$/.test(form.public_code) || !/^[-a-zA-Z0-9_]+$/.test(form.slug)) return "Enter a name, a four-character public code and a valid slug.";
    if (!organizationChosen) return "Choose an organization or enter a new organization name.";
    if (form.profile) {
      if (form.profile.timezone !== undefined) {
        try { new Intl.DateTimeFormat("en", { timeZone: form.profile.timezone }); } catch { return "Choose a valid timezone."; }
      }
      if (form.profile.default_currency !== undefined && !/^[a-z]{3}$/.test(form.profile.default_currency)) return "Enter a three-letter currency code.";
      const hoursError = form.profile.opening_hours === undefined ? null : validateHours(hoursDraft(form.profile.opening_hours));
      if (hoursError) return hoursError;
    }
    return null;
  };
  return <FlowLayout presentation="dialog" open={open} title={title} state={{ status: "ready" }}
    steps={steps.map((label, index) => ({ key: String(index), label, state: index < step ? "done" : index === step ? "current" : "todo" }))} current={String(step)}
    onCancel={() => { if (!pending) onClose(); }}
    footer={{ back: step > 0 ? { label: t`Back`, disabled: pending, disabledReason: t`Wait while your space is created.`, onClick: () => { setStep(step - 1); setInvalid(null); } } : undefined,
      next: { label: step === 4 ? title : t`Next`, pending, disabled: !organizationChosen, disabledReason: t`Choose an organization or enter a new organization name.`, pendingLabel: t`Creating…`, onClick: () => (document.getElementById("makerspace-creation-wizard") as HTMLFormElement)?.requestSubmit() } }}
    work={<>
    <p role="status" className="mb-3 text-sm">{t`Step ${step + 1} of ${steps.length}: ${steps[step]}`}</p>
    <form id="makerspace-creation-wizard" className="grid gap-3" onSubmit={event => {
      event.preventDefault(); if (pending) return;
      const message = validate(); setInvalid(message); if (message) return;
      if (step < 4) setStep(step + 1); else onSubmit();
    }}>
      <fieldset className="grid gap-3" disabled={pending}><legend className="sr-only">{steps[step]}</legend>{step === 0 ? <SpaceKindChooser value={form.kind ?? "makerspace"} onChange={kind => onChange({ ...form, kind })} /> : null}<CreationWizardSteps step={step} form={form} onChange={onChange} pending={pending} /></fieldset>
      {step === 0 && open ? <fieldset className="grid gap-3" disabled={pending}><OrganizationPicker form={form} error={error} onChange={onChange} /></fieldset> : null}
      {step === 0 && open && identityExtra ? <fieldset className="grid gap-3" disabled={pending}>{identityExtra}</fieldset> : null}
      <aside aria-label={t`${nounTitle} preview`} className="rounded-xl border border-dashed border-line bg-surface p-4"><p className="text-sm font-semibold text-muted">{t`${nounTitle} preview`}</p><h2 className="title-panel mt-2">{form.name || (organization ? t`Your organization` : t`Your makerspace`)}</h2><p className="mt-2 text-sm text-muted">/m/{form.slug || "your-space"} · {form.public_code || t`Public code`}</p><p className="mt-3 text-sm text-muted">{organization ? t`Your events, rooms and membership plans will appear here, on the organization page.` : t`Your catalogue will appear here.`}</p></aside>
      {invalid || error ? <p role="alert" className="text-sm text-danger">{invalid ?? (error instanceof Error ? error.message : t`Creation failed. Check the fields and retry.`)}</p> : null}
    </form>
  </>} />;
}
