import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Eye } from "lucide-react";
import { Callout, ConfirmDialog, SettingsRow, SettingsSection, StatusPill } from "../../../components/ui";
import { RouteLink } from "../../../components/ui/RouteLink";
import type { AccountProfile } from "../accountProfileTypes";
import { HandleField } from "./HandleField";
import { fieldError, usePatchProfile } from "./profileEditApi";
import { ProfilePreviewDialog } from "./ProfilePreviewDialog";
import { PublishConsentDialog } from "./PublishConsentDialog";
import { SectionToggle } from "./SectionToggle";

/**
 * Who can see the profile. Three separate decisions: the platform master switch (default on), the open-web switch
 * (default off, consent recorded when it turns on), and per-section switches (default on).
 */
export function VisibilityPanel({ profile }: { profile: AccountProfile }) {
  const patch = usePatchProfile();
  const handle = profile.handle ?? null;
  const visible = profile.is_visible !== false;
  const openWeb = Boolean(profile.public_visible);
  const [consenting, setConsenting] = useState(false);
  const [confirmOff, setConfirmOff] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const enable = () => patch.mutate({ public_visible: true, publication_consent: true }, { onSuccess: () => setConsenting(false) });
  return <SettingsSection title={t`Visibility`}
    description={t`Your profile is one page for your whole account. Choose who can see it, and which sections.`}>
    {profile.public_reconfirm_pending && !openWeb ? <div className="grid gap-2">
      <Callout size="banner" tone="warn" lead={t`Confirm the open web again.`}
        body={t`Your profiles from different spaces were combined into one, so publishing it to logged-out visitors and search engines is off until you confirm it.`}
        action={handle ? { label: t`Publish on the open web`, onClick: () => { patch.reset(); setConsenting(true); } } : undefined} />
      <button type="button" className="w-fit text-sm font-semibold text-accent-ink underline-offset-2 hover:underline" disabled={patch.isPending}
        onClick={() => patch.mutate({ public_visible: false })}>{t`Keep it off the open web`}</button>
    </div> : null}
    <SettingsRow label={t`Handle`} helper={t`Your username and profile address. One per account.`} htmlFor="profile-handle">
      <HandleField handle={handle} />
    </SettingsRow>
    <SettingsRow label={t`On the platform`} helper={t`Signed-in members of every space can open your profile. Switching this off hides it everywhere, and the space member directory lists you as hidden.`}>
      <label htmlFor="profile-master" className="flex min-h-11 cursor-pointer items-center gap-3 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus">
        <input id="profile-master" type="checkbox" role="switch" className="h-5 w-5 accent-accent" checked={visible} disabled={patch.isPending}
          onChange={() => patch.mutate({ is_visible: !visible })} />
        <span className="text-sm font-semibold text-ink">{t`Show my profile on the platform`}</span>
      </label>
    </SettingsRow>
    <SettingsRow label={t`On the open web`}
      helper={t`Off by default. When on, logged-out visitors and search engines can see the sections you show, with a share card. This needs your consent.`}>
      <div className="grid gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone={openWeb ? "success" : "neutral"} label={openWeb ? t`On the open web` : t`Not on the open web`} />
          {openWeb && handle ? <RouteLink href={`/${handle}`} className="font-semibold text-accent-ink underline-offset-2 hover:underline">{t`View open-web page ↗`}</RouteLink> : null}
        </div>
        <label htmlFor="profile-open-web" className="flex min-h-11 cursor-pointer items-start gap-3 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus">
          <input id="profile-open-web" type="checkbox" role="switch" className="mt-0.5 h-5 w-5 accent-accent" checked={openWeb}
            disabled={!handle || patch.isPending} aria-describedby="profile-open-web-hint"
            onChange={() => { if (openWeb) setConfirmOff(true); else { patch.reset(); setConsenting(true); } }} />
          <span className="grid">
            <span className="text-sm font-semibold text-ink">{t`Also show it on the open web (logged-out visitors, search engines)`}</span>
            <span id="profile-open-web-hint" className="text-sm text-muted">{!handle ? t`Choose your handle first; the open web needs an address.`
              : openWeb && profile.public_consented_at ? t`You consented on ${new Date(profile.public_consented_at).toLocaleDateString(formatLocale())}.`
              : t`Turning this on asks for your consent.`}</span>
          </span>
        </label>
        {patch.error && !consenting ? <p role="alert" className="text-sm text-danger">{fieldError(patch.error, "public_visible")}</p> : null}
      </div>
    </SettingsRow>
    <SettingsRow label={t`Sections that fill themselves`} helper={t`Built from your activity. Each starts on; switch one off to hide it.`}>
      <div className="grid gap-1">
        <SectionToggle section="events" label={t`Events I attended`} />
        <SectionToggle section="spaces" label={t`Spaces and organizations I belong to`} />
        <SectionToggle section="certifications" label={t`Certifications`} />
      </div>
    </SettingsRow>
    <SettingsRow label={t`Preview`} helper={t`See your profile as another member would.`}>
      <button type="button" className="desk-button w-fit gap-2" onClick={() => setPreviewing(true)}><Eye aria-hidden="true" className="h-4 w-4" />{t`Preview`}</button>
    </SettingsRow>
    <PublishConsentDialog open={consenting} handle={handle ?? ""} pending={patch.isPending}
      error={patch.error ? fieldError(patch.error, "publication_consent") : undefined} onCancel={() => setConsenting(false)} onPublish={enable} />
    <ConfirmDialog open={confirmOff} tone="danger" title={t`Take your profile off the open web?`} confirmLabel={t`Turn off`}
      message={t`Logged-out visitors and search engines lose access straight away. Turning it on again asks for your consent again.`}
      pending={patch.isPending} onCancel={() => setConfirmOff(false)}
      onConfirm={() => patch.mutate({ public_visible: false }, { onSettled: () => setConfirmOff(false) })} />
    <ProfilePreviewDialog open={previewing} onClose={() => setPreviewing(false)} profile={profile} />
  </SettingsSection>;
}
