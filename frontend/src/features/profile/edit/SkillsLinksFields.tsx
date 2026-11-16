import { t } from "@lingui/core/macro";
import { SettingsSection } from "../../../components/ui";
import { Field } from "../../members/memberProfile/Field";
import { LinksField, SkillsField } from "../../members/memberProfile/PublicContentFields";
import type { ProfileDraft } from "./profileDraft";
import { SectionToggle } from "./SectionToggle";

/** Skills (with their domains), links, interests and languages: each has its own show switch. */
export function SkillsLinksFields({ draft, onChange }: { draft: ProfileDraft; onChange: (changes: Partial<ProfileDraft>) => void }) {
  return <>
    <SettingsSection title={t`Skills`}>
      <Field id="profile-domains" label={t`Domains`} hint={t`What you work in, comma separated. Shown as chips.`}>
        <input id="profile-domains" className="desk-input w-full" value={draft.domains} onChange={event => onChange({ domains: event.target.value })} />
      </Field>
      <SkillsField skills={draft.skills} onChange={skills => onChange({ skills })} />
      <div className="py-3"><SectionToggle section="skills" label={t`Show my skills`} /></div>
    </SettingsSection>
    <SettingsSection title={t`Links`}>
      <LinksField links={draft.links} onChange={links => onChange({ links })} />
      <div className="py-3"><SectionToggle section="links" label={t`Show my links`} /></div>
    </SettingsSection>
    <SettingsSection title={t`Interests and languages`}>
      <Field id="profile-interests" label={t`Interests`} hint={t`Comma separated`}>
        <input id="profile-interests" className="desk-input w-full" value={draft.interests} onChange={event => onChange({ interests: event.target.value })} />
      </Field>
      <Field id="profile-languages" label={t`Languages`} hint={t`Comma separated`}>
        <input id="profile-languages" className="desk-input w-full" value={draft.languages} onChange={event => onChange({ languages: event.target.value })} />
      </Field>
      <div className="py-3"><SectionToggle section="interests" label={t`Show my interests and languages`} /></div>
    </SettingsSection>
  </>;
}
