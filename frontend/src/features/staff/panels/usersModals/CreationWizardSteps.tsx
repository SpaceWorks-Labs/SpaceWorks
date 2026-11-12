import { t } from "@lingui/core/macro";
import { Field } from "../../../../components/ui";
import { MakerspaceHoursEditor } from "../../MakerspaceHoursEditor";
import { hoursDraft, serializeHours } from "../../makerspaceProfileForm";
import { SpacePackProfilePicker } from "../../SpacePackProfilePicker";
import type { MakerspaceForm } from "./types";
import { moduleLabel, moduleList } from "../../../../lib/moduleLabels";
import { spaceNoun, spaceNounTitle } from "../../../../lib/spaceNoun";

export const defaultCreationProfile = { timezone: "UTC", country: "", default_currency: "usd", opening_hours: {} };
const modules = ["events", "bookings", "machines", "machine_service", "membership", "payments", "reports", "notifications"] as const;

const PROFILE_LABELS = (): Record<string, string> => ({ timezone: t`Timezone`, country: t`Country code`, default_currency: t`Currency` });

export function CreationWizardSteps({ step, form, onChange, pending }: { step: number; form: MakerspaceForm; onChange: (form: MakerspaceForm) => void; pending: boolean }) {
  const profile = { ...defaultCreationProfile, ...form.profile };
  const kind = form.kind ?? "makerspace";
  const noun = spaceNoun(kind);
  if (step === 0) return <>
    {(["name", "public_code", "slug", "location"] as const).map(key => <Field key={key} label={{ name: t`Name`, public_code: t`Public code`, slug: t`Slug`, location: t`Location` }[key]} hint={key === "public_code" ? t`Four letters or numbers, shown on labels and receipts.` : key === "slug" ? t`Your public address: …/m/` : undefined}>
      <input className="desk-input w-full" required={key !== "location"} pattern={key === "public_code" ? "[A-Z0-9]{4}" : key === "slug" ? "[-a-zA-Z0-9_]+" : undefined} title={key === "public_code" ? t`Use four uppercase letters or numbers.` : key === "slug" ? t`Use letters, numbers, hyphens or underscores.` : undefined} maxLength={key === "public_code" ? 4 : key === "slug" ? 50 : 200} value={form[key]} onChange={event => onChange({ ...form, [key]: key === "public_code" ? event.target.value.toUpperCase() : event.target.value })} />
    </Field>)}
    <p className="text-xs text-muted">{t`Create with platform access enabled. Hidden spaces require two verified archive recipients before access can be disabled.`}</p>
  </>;
  if (step === 1) return <>
    <p className="text-sm text-muted">{t`Leave these unchanged to use the deployment or saved pack profile. Editing them explicitly overrides the pack.`}</p>
    {(["timezone", "country", "default_currency"] as const).map(key => <Field key={key} label={{ timezone: t`Timezone`, country: t`Country code`, default_currency: t`Currency` }[key]}>
      <input className="desk-input w-full" value={profile[key]} maxLength={key === "timezone" ? 100 : key === "country" ? 2 : 3} onChange={event => onChange({ ...form, profile: { ...form.profile, [key]: key === "country" ? event.target.value.toUpperCase() : key === "default_currency" ? event.target.value.toLowerCase() : event.target.value } })} />
    </Field>)}
    <MakerspaceHoursEditor value={hoursDraft(profile.opening_hours)} onChange={hours => onChange({ ...form, profile: { ...form.profile, opening_hours: serializeHours(hours) } })} />
  </>;
  if (step === 2) return <>
    <SpacePackProfilePicker value={form.install_profile_id ?? ""} disabled={pending} onChange={pack => onChange({ ...form, install_profile_id: pack?.id ?? "" })} />
    <p className="text-sm text-muted">{t`Core modules remain installed. The server adds dependencies and refuses modules this deployment does not ship.`}</p>
    {kind === "organization" && !form.modules ? <p className="text-sm text-ink">{t`An organization workspace starts with Events, Memberships (with ID cards) and Bookings. Inventory and Machines stay off until you turn them on.`}</p> : null}
    <label className="flex min-h-11 gap-2"><input type="checkbox" checked={form.modules !== undefined} onChange={event => onChange({ ...form, modules: event.target.checked ? [] : undefined })} />{t`Choose module families instead of the deployment or saved pack defaults`}</label>
    {form.modules ? <div className="grid gap-3 sm:grid-cols-2">{modules.map(key => <label key={key} className="flex min-h-11 items-center gap-3 rounded-xl border border-line p-4 has-checked:border-accent has-checked:bg-accent-soft"><input type="checkbox" checked={form.modules!.includes(key)} onChange={event => onChange({ ...form, modules: event.target.checked ? [...form.modules!, key] : form.modules!.filter(value => value !== key) })} />{moduleLabel(key)}</label>)}</div> : null}
  </>;
  if (step === 3) return <>
    <p className="text-sm text-muted">{t`After creating the ${noun}, create its first Space Manager account. They can set their password by email invitation, or you can issue a one-time password.`}</p>
  </>;
  return <dl className="grid gap-2 text-sm"><dt>{t`Kind`}</dt><dd>{spaceNounTitle(kind)}</dd><dt>{t`Name`}</dt><dd>{form.name}</dd><dt>{t`Organization`}</dt><dd>{form.organization === "new" ? t`${form.organization_name ?? form.name} (new)` : form.organization?.name}</dd><dt>{t`Public address`}</dt><dd>/m/{form.slug}</dd><dt>{t`Profile overrides`}</dt><dd>{form.profile ? Object.entries(form.profile).map(([key, value]) => key === "opening_hours" ? t`Opening hours` : `${PROFILE_LABELS()[key] ?? key}: ${value}`).join(", ") : t`Deployment or saved pack defaults`}</dd><dt>{t`Modules`}</dt><dd>{moduleList(form.modules ?? []) || (form.modules ? t`Core only` : kind === "organization" ? t`Events, Memberships and Bookings` : t`Deployment or saved pack defaults`)}</dd><dt>{t`Saved pack`}</dt><dd>{form.install_profile_id || t`None`}</dd><dt>{t`First staff`}</dt><dd>{t`Create a Space Manager account next`}</dd></dl>;
}
