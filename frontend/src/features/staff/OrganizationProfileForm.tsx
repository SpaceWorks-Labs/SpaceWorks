import { t } from "@lingui/core/macro";
import { useEffect, useState, type FormEvent } from "react";
import { SettingsActions, SettingsRow } from "../../components/ui";

import type { OrganizationDetail } from "./organizationsApi";
import { useUpdateOrganization } from "./organizationsApi";

export function OrganizationProfileForm({ organization }: { organization: OrganizationDetail }) {
  const [values, setValues] = useState({
    name: organization.name,
    slug: organization.slug,
    description: organization.description,
    website: organization.website,
    public_profile_enabled: organization.public_profile_enabled,
    is_discoverable: organization.is_discoverable ?? false,
  });
  const update = useUpdateOrganization(organization.id, organization.slug);
  const allowed = organization.governance_actions.includes("manage_organization_profile");
  const original = { name: organization.name, slug: organization.slug, description: organization.description, website: organization.website, public_profile_enabled: organization.public_profile_enabled, is_discoverable: organization.is_discoverable ?? false };
  const dirty = JSON.stringify(values) !== JSON.stringify(original);

  useEffect(() => {
    setValues({
      name: organization.name,
      slug: organization.slug,
      description: organization.description,
      website: organization.website,
      public_profile_enabled: organization.public_profile_enabled,
      is_discoverable: organization.is_discoverable ?? false,
    });
  }, [organization]);

  function submit(event: FormEvent) {
    event.preventDefault();
    update.mutate(values);
  }

  return (
    <form className="grid divide-y divide-line" onSubmit={submit}>
      <div className="mb-3">
        <h3 className="title-section">{t`Public profile`}</h3>
        <p className="mt-1 text-sm text-muted">{t`Controls the organization directory page. The platform operator handles logo uploads.`}</p>
      </div>
        <SettingsRow label={t`Name`} htmlFor="organization-name">
          <input id="organization-name" className="desk-input w-full" maxLength={200} disabled={!allowed} value={values.name} onChange={(event) => setValues({ ...values, name: event.target.value })} />
        </SettingsRow>
        <SettingsRow label={t`Public slug`} htmlFor="organization-slug" helper={t`Public page: /o/${values.slug}`}>
          <input id="organization-slug" className="desk-input w-full" disabled={!allowed} value={values.slug} onChange={(event) => setValues({ ...values, slug: event.target.value })} />
        </SettingsRow>
        <SettingsRow label={t`Website`} htmlFor="organization-website">
          <input id="organization-website" className="desk-input w-full" type="url" disabled={!allowed} value={values.website} onChange={(event) => setValues({ ...values, website: event.target.value })} />
        </SettingsRow>
        <SettingsRow label={t`Description`} htmlFor="organization-description">
          <textarea id="organization-description" className="desk-input min-h-28 w-full" disabled={!allowed} value={values.description} onChange={(event) => setValues({ ...values, description: event.target.value })} />
        </SettingsRow>
        <SettingsRow label={t`Listed publicly`} helper={t`Show the organization profile and eligible event catalogue.`}><label className="flex min-h-11 items-center gap-3 text-sm text-ink">
          <input type="checkbox" disabled={!allowed} checked={values.public_profile_enabled} onChange={(event) => setValues({ ...values, public_profile_enabled: event.target.checked })} />
          {t`Publish this organization profile and its eligible event catalogue`}</label></SettingsRow>
        <SettingsRow label={t`Findable by event organizers`} helper={t`Off by default. When on, staff at other makerspaces can find this organization and invite its members to their events. It gives them no access to the organization.`}><label className="flex min-h-11 items-center gap-3 text-sm text-ink">
          <input type="checkbox" disabled={!allowed} checked={values.is_discoverable} onChange={(event) => setValues({ ...values, is_discoverable: event.target.checked })} />
          {t`List this organization in the event organizer directory`}</label></SettingsRow>
      {allowed && dirty ? <div className="sticky bottom-0 z-10 bg-panel pb-[env(safe-area-inset-bottom)]"><SettingsActions onDiscard={() => setValues(original)} onSave={() => (document.getElementById("organization-name")?.closest("form") as HTMLFormElement)?.requestSubmit()} pending={update.isPending} /></div> : !allowed ? <p className="mt-4 text-sm text-muted">{t`You have view-only access to this profile.`}</p> : null}
      {update.error ? <p className="mt-2 text-sm text-danger" role="alert">{update.error.message}</p> : null}
    </form>
  );
}
