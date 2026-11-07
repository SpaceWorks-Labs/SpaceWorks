import { t } from "@lingui/core/macro";
import { Field } from "../../../../components/ui";
import { MakerspaceHoursEditor } from "../../MakerspaceHoursEditor";
import { hoursDraft, serializeHours } from "../../makerspaceProfileForm";
import { SpacePackProfilePicker } from "../../SpacePackProfilePicker";
import type { MakerspaceForm } from "./types";

export const defaultCreationProfile = { timezone: "UTC", country: "", default_currency: "usd", opening_hours: {} };
const modules = [["events", "Events"], ["bookings", "Bookings"], ["machines", "Machines"], ["membership", "Membership"], ["printing", "Printing"], ["payments", "Online payments"], ["reports", "Reports"], ["notifications", "Notifications"]] as const;

export function CreationWizardSteps({ step, form, onChange, pending }: { step: number; form: MakerspaceForm; onChange: (form: MakerspaceForm) => void; pending: boolean }) {
  const profile = { ...defaultCreationProfile, ...form.profile };
  if (step === 0) return <>
    {(["name", "public_code", "slug", "location"] as const).map(key => <Field key={key} label={{ name: "Name", public_code: "Public code", slug: "Slug", location: "Location" }[key]} hint={key === "public_code" ? t`Four letters or numbers, shown on labels and receipts.` : key === "slug" ? t`Your public address: …/m/` : undefined}>
      <input className="desk-input w-full" required={key !== "location"} pattern={key === "public_code" ? "[A-Z0-9]{4}" : key === "slug" ? "[-a-zA-Z0-9_]+" : undefined} title={key === "public_code" ? t`Use four uppercase letters or numbers.` : key === "slug" ? t`Use letters, numbers, hyphens or underscores.` : undefined} maxLength={key === "public_code" ? 4 : key === "slug" ? 50 : 200} value={form[key]} onChange={event => onChange({ ...form, [key]: key === "public_code" ? event.target.value.toUpperCase() : event.target.value })} />
    </Field>)}
    <p className="text-xs text-muted">{t`Create with platform access enabled. Hidden spaces require two verified archive recipients before access can be disabled.`}</p>
  </>;
  if (step === 1) return <>
    <p className="text-sm text-muted">{t`Leave these unchanged to use the deployment or saved pack profile. Editing them explicitly overrides the pack.`}</p>
    {(["timezone", "country", "default_currency"] as const).map(key => <Field key={key} label={{ timezone: "Timezone", country: "Country code", default_currency: "Currency" }[key]}>
      <input className="desk-input w-full" value={profile[key]} maxLength={key === "timezone" ? 100 : key === "country" ? 2 : 3} onChange={event => onChange({ ...form, profile: { ...form.profile, [key]: key === "country" ? event.target.value.toUpperCase() : key === "default_currency" ? event.target.value.toLowerCase() : event.target.value } })} />
    </Field>)}
    <MakerspaceHoursEditor value={hoursDraft(profile.opening_hours)} onChange={hours => onChange({ ...form, profile: { ...form.profile, opening_hours: serializeHours(hours) } })} />
  </>;
  if (step === 2) return <>
    <SpacePackProfilePicker value={form.install_profile_id ?? ""} disabled={pending} onChange={pack => onChange({ ...form, install_profile_id: pack?.id ?? "" })} />
    <p className="text-sm text-muted">{t`Core modules remain installed. The server adds dependencies and refuses modules this deployment does not ship.`}</p>
    <label className="flex min-h-11 gap-2"><input type="checkbox" checked={form.modules !== undefined} onChange={event => onChange({ ...form, modules: event.target.checked ? [] : undefined })} />{t`Choose module families instead of the deployment or saved pack defaults`}</label>
    {form.modules ? <div className="grid gap-3 sm:grid-cols-2">{modules.map(([key, label]) => <label key={key} className="flex min-h-11 items-center gap-3 rounded-xl border border-line p-4 has-checked:border-accent has-checked:bg-accent-soft"><input type="checkbox" checked={form.modules!.includes(key)} onChange={event => onChange({ ...form, modules: event.target.checked ? [...form.modules!, key] : form.modules!.filter(value => value !== key) })} />{label}</label>)}</div> : null}
  </>;
  if (step === 3) return <>
    <p className="text-sm text-muted">{t`After creating the makerspace, create its first Space Manager account. They can set their password by email invitation, or you can issue a one-time password.`}</p>
  </>;
  return <dl className="grid gap-2 text-sm"><dt>{t`Name`}</dt><dd>{form.name}</dd><dt>{t`Organization`}</dt><dd>{form.organization === "new" ? `${form.organization_name ?? form.name} (new)` : form.organization?.name}</dd><dt>{t`Public address`}</dt><dd>/m/{form.slug}</dd><dt>{t`Profile overrides`}</dt><dd>{form.profile ? Object.entries(form.profile).map(([key, value]) => key === "opening_hours" ? "Opening hours" : `${key}: ${value}`).join(", ") : t`Deployment or saved pack defaults`}</dd><dt>{t`Modules`}</dt><dd>{form.modules?.join(", ") || (form.modules ? t`Core only` : t`Deployment or saved pack defaults`)}</dd><dt>{t`Saved pack`}</dt><dd>{form.install_profile_id || t`None`}</dd><dt>{t`First staff`}</dt><dd>{t`Create a Space Manager account next`}</dd></dl>;
}
