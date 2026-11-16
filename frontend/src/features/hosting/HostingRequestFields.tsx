import { t } from "@lingui/core/macro";
import { Field } from "../../components/ui";
import type { HostingFormKey, HostingFormValue } from "./hostingForm";

type Props = {
  value: HostingFormValue;
  onChange: (key: HostingFormKey, value: string) => void;
  errors: Record<string, string>;
  /** The invite page owns the organization choice and renders this field itself. */
  showOrganizationName?: boolean;
  /** Only the open request form asks for the expected size; the invitation form does not send it. */
  showExpectedMembers?: boolean;
};

/**
 * The applicant fields shared by the open hosting form and the invitation form. `website` is the
 * honeypot the backend checks first: a filled value gets the same acknowledgement and stores
 * nothing, so it is rendered display:none, out of the tab order and out of autofill.
 */
export function HostingRequestFields({ value, onChange, errors, showOrganizationName = true, showExpectedMembers = false }: Props) {
  const input = (key: HostingFormKey) => ({
    className: "desk-input",
    value: value[key],
    onChange: (event: { target: { value: string } }) => onChange(key, event.target.value),
  });
  const descriptionLength = value.description.trim().length;
  const organization = value.requested_kind === "organization";
  return <div className="grid gap-4">
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`Your name`} error={errors.applicant_name}>
        <input {...input("applicant_name")} required minLength={2} maxLength={200} autoComplete="name" />
      </Field>
      <Field label={t`Email`} error={errors.applicant_email}>
        <input {...input("applicant_email")} required type="email" maxLength={254} autoComplete="email" />
      </Field>
      <Field label={t`Phone (optional)`} error={errors.applicant_phone}>
        <input {...input("applicant_phone")} type="tel" maxLength={32} autoComplete="tel" />
      </Field>
      <Field label={organization ? t`Organization name` : t`Makerspace name`} error={errors.space_name}>
        <input {...input("space_name")} required minLength={2} maxLength={200} autoComplete="organization" />
      </Field>
      {organization ? <Field label={t`Where you meet (optional)`} hint={t`A city or venue, if you have one. Leave empty for an online group.`} error={errors.location}>
        <input {...input("location")} minLength={2} maxLength={200} />
      </Field> : <Field label={t`Location`} hint={t`City and country, or the campus it sits on.`} error={errors.location}>
        <input {...input("location")} required minLength={2} maxLength={200} />
      </Field>}
      <Field label={organization ? t`Website (optional)` : t`Space website (optional)`} error={errors.space_website_url}>
        <input {...input("space_website_url")} type="url" maxLength={200} placeholder="https://" autoComplete="url" />
      </Field>
      {showExpectedMembers ? <Field label={t`Expected members (optional)`} hint={organization ? t`Roughly how many members you have.` : t`Roughly how many people will use the space.`} error={errors.expected_members}>
        <input {...input("expected_members")} type="number" min={1} max={100000} step={1} inputMode="numeric" />
      </Field> : null}
    </div>
    <Field label={organization ? t`About your organization` : t`About your space`} error={errors.description}
      hint={organization ? t`${descriptionLength}/2000 characters · at least 20. Who your members are, what you run and what you'd use Space Works for.`
        : t`${descriptionLength}/2000 characters · at least 20. What you make, who uses it and what you'd run on Space Works.`}>
      <textarea {...input("description")} className="desk-input min-h-32" required minLength={20} maxLength={2000} />
    </Field>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`Suggested web address (optional)`} hint={t`Lowercase letters, numbers and hyphens, like north-lab.`} error={errors.proposed_slug}>
        <input {...input("proposed_slug")} maxLength={50} pattern="[a-z0-9]+(-[a-z0-9]+)*" autoCapitalize="none" spellCheck={false} />
      </Field>
      {showOrganizationName && !organization ? <Field label={t`Organization name (optional)`} hint={t`The group that runs the space, if it has one.`}
        error={errors.new_organization_name}>
        <input {...input("new_organization_name")} maxLength={200} />
      </Field> : null}
    </div>
    <div className="hidden" aria-hidden="true">
      <label>
        {t`Website`}<input name="website" tabIndex={-1} autoComplete="off" value={value.website} onChange={(event) => onChange("website", event.target.value)} />
      </label>
    </div>
  </div>;
}
