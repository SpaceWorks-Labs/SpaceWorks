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
  return <div className="grid gap-4">
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Your name" error={errors.applicant_name}>
        <input {...input("applicant_name")} required minLength={2} maxLength={200} autoComplete="name" />
      </Field>
      <Field label="Email" error={errors.applicant_email}>
        <input {...input("applicant_email")} required type="email" maxLength={254} autoComplete="email" />
      </Field>
      <Field label="Phone (optional)" error={errors.applicant_phone}>
        <input {...input("applicant_phone")} type="tel" maxLength={32} autoComplete="tel" />
      </Field>
      <Field label="Makerspace name" error={errors.space_name}>
        <input {...input("space_name")} required minLength={2} maxLength={200} autoComplete="organization" />
      </Field>
      <Field label="Location" hint="City and country, or the campus it sits on." error={errors.location}>
        <input {...input("location")} required minLength={2} maxLength={200} />
      </Field>
      <Field label="Space website (optional)" error={errors.space_website_url}>
        <input {...input("space_website_url")} type="url" maxLength={200} placeholder="https://" autoComplete="url" />
      </Field>
      {showExpectedMembers ? <Field label="Expected members (optional)" hint="Roughly how many people will use the space." error={errors.expected_members}>
        <input {...input("expected_members")} type="number" min={1} max={100000} step={1} inputMode="numeric" />
      </Field> : null}
    </div>
    <Field label="About your space" error={errors.description}
      hint={`${descriptionLength}/2000 characters · at least 20. What you make, who uses it and what you'd run on Space Works.`}>
      <textarea {...input("description")} className="desk-input min-h-32" required minLength={20} maxLength={2000} />
    </Field>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Suggested web address (optional)" hint="Lowercase letters, numbers and hyphens, like north-lab." error={errors.proposed_slug}>
        <input {...input("proposed_slug")} maxLength={50} pattern="[a-z0-9]+(-[a-z0-9]+)*" autoCapitalize="none" spellCheck={false} />
      </Field>
      {showOrganizationName ? <Field label="Organization name (optional)" hint="The group that runs the space, if it has one."
        error={errors.new_organization_name}>
        <input {...input("new_organization_name")} maxLength={200} />
      </Field> : null}
    </div>
    <div className="hidden" aria-hidden="true">
      <label>
        Website
        <input name="website" tabIndex={-1} autoComplete="off" value={value.website} onChange={(event) => onChange("website", event.target.value)} />
      </label>
    </div>
  </div>;
}
