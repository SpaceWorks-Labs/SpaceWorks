import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ErrorBlock, SettingsActions, SettingsSection } from "../../../components/ui";
import { memberRequest } from "../../../lib/api";
import { isPublicLink } from "../../members/memberProfile/PublicContentFields";
import { ImageUploader } from "../../staff/ImageUploader";
import type { AccountProfile } from "../accountProfileTypes";
import { ActivityFields } from "./ActivityFields";
import { AchievementsEditor } from "./AchievementsEditor";
import { draftToPatch, seedDraft, type ProfileDraft } from "./profileDraft";
import { fieldError, ownProfileKey, useOwnProfile, usePatchProfile } from "./profileEditApi";
import { ProjectsFields } from "./ProjectsFields";
import { SkillsLinksFields } from "./SkillsLinksFields";
import { StatusAboutFields } from "./StatusAboutFields";
import { TimelineEditor } from "./TimelineEditor";
import { VisibilityPanel } from "./VisibilityPanel";
import { LogoLoader } from "../../../components/LogoLoader";

/** The text fields share one "Save changes" form; switches, handle, timeline and achievements save on their own. */
function ProfileForm({ profile }: { profile: AccountProfile }) {
  const client = useQueryClient();
  const patch = usePatchProfile();
  const [draft, setDraft] = useState<ProfileDraft>(() => seedDraft(profile));
  // Set by any edit, cleared by a save or discard. An avatar upload refetches the profile; a dirty form must keep its text.
  const [dirty, setDirty] = useState(false);
  useEffect(() => { if (!dirty) setDraft(seedDraft(profile)); }, [profile, dirty]);
  const edit = (changes: Partial<ProfileDraft>) => { setDirty(true); setDraft(current => ({ ...current, ...changes })); };
  const badLink = draft.links.some(link => link.url.trim() !== "" && !isPublicLink(link.url.trim()));
  const save = () => patch.mutate(draftToPatch(draft), { onSuccess: () => setDirty(false) });
  return <div className="grid gap-5">
    <SettingsSection title={t`Photo`}>
      <div className="py-4"><ImageUploader request={memberRequest} endpoint="/member/profile/image" currentUrl={profile.avatar_url} label={t`Avatar`}
        onChanged={() => { void client.invalidateQueries({ queryKey: ownProfileKey }); }} /></div>
    </SettingsSection>
    <StatusAboutFields draft={draft} onChange={edit} />
    <ProjectsFields projects={draft.projects} saved={profile.projects} onChange={projects => edit({ projects })} />
    <SkillsLinksFields draft={draft} onChange={edit} />
    <ActivityFields draft={draft} onChange={edit} githubVerified={Boolean(profile.github_verified)} savedGithub={profile.github_username ?? ""} />
    {patch.error ? <p role="alert" className="text-sm text-danger">{fieldError(patch.error, "detail")}</p> : null}
    {dirty || patch.isPending ? <SettingsActions pending={patch.isPending} disabled={badLink} onSave={save}
      onDiscard={() => { setDirty(false); setDraft(seedDraft(profile)); patch.reset(); }} /> : null}
  </div>;
}

/** The account-level profile editor: one profile per person, shown across every space. */
export function GlobalProfileEditor() {
  const profile = useOwnProfile();
  if (profile.isLoading) return <LogoLoader label={t`Loading your profile…`} size={48} className="min-h-48 py-3" />;
  if (profile.error || !profile.data) return <ErrorBlock error={new Error(profile.error instanceof Error ? profile.error.message : t`Unable to load your profile.`)} onRetry={() => { void profile.refetch(); }} />;
  return <div className="grid gap-5">
    <VisibilityPanel profile={profile.data} />
    <ProfileForm profile={profile.data} />
    <TimelineEditor />
    <AchievementsEditor profile={profile.data} />
  </div>;
}
