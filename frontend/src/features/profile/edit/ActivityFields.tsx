import { t } from "@lingui/core/macro";
import { SettingsSection } from "../../../components/ui";
import { Field } from "../../members/memberProfile/Field";
import type { ProfileDraft } from "./profileDraft";
import { SectionToggle } from "./SectionToggle";

/**
 * The account-level activity graph: counts only, across all your spaces. Projects and events default on; speaking,
 * machine jobs, bookings and loans default off, and each is its own consent. Your GitHub calendar shows only while the graph is on.
 */
export function ActivityFields({ draft, onChange, githubVerified = false, savedGithub = "" }: {
  draft: ProfileDraft; onChange: (changes: Partial<ProfileDraft>) => void; githubVerified?: boolean; savedGithub?: string;
}) {
  return <SettingsSection title={t`Activity graph`} description={t`Daily counts only, never what happened. Counted across every space you belong to.`}>
    <div className="grid gap-1 py-4">
      <SectionToggle section="activity_graph" label={t`Show my activity graph`} />
      <SectionToggle section="projects" label={t`Count projects`} />
      <SectionToggle section="events" label={t`Count events`} />
      <SectionToggle section="speaking" label={t`Count speaking`} />
      <SectionToggle section="machine_activity" label={t`Count machine jobs`} />
      <SectionToggle section="bookings" label={t`Count bookings`} />
      <SectionToggle section="loans" label={t`Count loans`} />
    </div>
    <Field id="profile-github" label={t`GitHub username`} hint={t`Adds your GitHub contribution calendar next to this graph once you have linked that GitHub account.`}>
      <input id="profile-github" className="desk-input w-full" maxLength={39} autoCapitalize="none" spellCheck={false} value={draft.github} onChange={event => onChange({ github: event.target.value })} />
    </Field>
    {savedGithub && !githubVerified ? <p className="text-sm text-muted" data-testid="github-unverified">
      {t`Unverified: visitors see your GitHub name as a plain link, with no badge or calendar. To verify it, link GitHub as a sign-in method in your account settings; it must be the same GitHub account.`}
    </p> : null}
  </SettingsSection>;
}
