import { t } from "@lingui/core/macro";
import { useState } from "react";
import { SettingsRow, SettingsSection } from "../../../components/ui";
import { RouteLink } from "../../../components/ui/RouteLink";
import type { AccountProfile } from "../accountProfileTypes";
import { HandleField } from "./HandleField";
import { ProfilePreviewDialog } from "./ProfilePreviewDialog";
import { SectionToggle } from "./SectionToggle";

/** Decision 549: publication is always on; project choices remain editable. */
export function VisibilityPanel({ profile }: { profile: AccountProfile }) {
  const [previewing, setPreviewing] = useState(false);
  return <SettingsSection title={t`Public profile`}
    description={t`Your profile is always public when you have a handle. It shows your name, avatar, bio, published projects and active memberships in public spaces.`}>
    <SettingsRow label={t`Handle`} helper={t`Your username and profile address. One per account.`} htmlFor="profile-handle">
      <HandleField handle={profile.handle} />
    </SettingsRow>
    <p className="py-3 text-sm text-muted">{t`Minors and restricted or suspended accounts show only their name and avatar. Contact details and private activity are never shown.`}</p>
    {profile.handle ? <RouteLink href={`/@${profile.handle}`} className="desk-button w-fit">{t`View public profile`}</RouteLink> : null}
    <SettingsRow label={t`Signed-in profile sections`} helper={t`These choices apply to your richer account profile. Public memberships are always listed when eligible.`}>
      <div className="grid gap-1">
        <SectionToggle section="events" label={t`Events I attended`} />
        <SectionToggle section="certifications" label={t`Certifications`} />
      </div>
    </SettingsRow>
    <SettingsRow label={t`Preview`} helper={t`See your profile as another member would.`}>
      <button type="button" className="desk-button w-fit" onClick={() => setPreviewing(true)}>{t`Preview`}</button>
    </SettingsRow>
    <ProfilePreviewDialog open={previewing} onClose={() => setPreviewing(false)} profile={profile} />
  </SettingsSection>;
}
