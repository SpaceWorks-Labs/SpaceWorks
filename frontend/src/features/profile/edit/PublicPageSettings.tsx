import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Eye } from "lucide-react";
import { ConfirmDialog, SettingsRow, SettingsSection, StatusPill } from "../../../components/ui";
import { RouteLink } from "../../../components/ui/RouteLink";
import type { MemberProfile } from "../../members/memberProfile/types";
import { HandleField } from "./HandleField";
import { fieldError, usePatchPublication, useTimeline } from "./profileEditApi";
import { ProfilePreviewDialog } from "./ProfilePreviewDialog";
import { PublishConsentDialog } from "./PublishConsentDialog";
import { VisibilitySwitches } from "./VisibilitySwitches";

/**
 * The public page at /<handle>: separate from the member directory, published only through
 * an explicit consent step, and with every section behind its own switch.
 */
export function PublicPageSettings({ makerspaceId, profile }: { makerspaceId: number; profile: MemberProfile }) {
  const handle = profile.handle ?? null;
  const published = Boolean(profile.public_visible);
  const publication = usePatchPublication(makerspaceId);
  const timeline = useTimeline(makerspaceId);
  const [consenting, setConsenting] = useState(false);
  const [confirmUnpublish, setConfirmUnpublish] = useState(false);
  const [previewing, setPreviewing] = useState(false);

  const publish = () => publication.mutate({ public_visible: true, publication_consent: true }, { onSuccess: () => setConsenting(false) });
  return <SettingsSection title={t`Public profile page`}
    description={t`A page anyone can open at your own address. It is separate from the member directory and stays offline until you publish it.`}>
    <SettingsRow label={t`Handle`} helper={t`Your public address. One per account.`} htmlFor={`profile-handle-${makerspaceId}`}>
      <HandleField makerspaceId={makerspaceId} handle={handle} />
    </SettingsRow>
    <SettingsRow label={t`Publication`} helper={published && profile.public_consented_at
      ? t`Published with your consent on ${new Date(profile.public_consented_at).toLocaleDateString(formatLocale())}.` : t`Only you can publish, and only after confirming.`}>
      <div className="grid gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone={published ? "success" : "neutral"} label={published ? t`Published` : t`Not published`} />
          {published && handle ? <RouteLink href={`/${handle}`} className="font-semibold text-accent-ink underline-offset-2 hover:underline">{t`View public page ↗`}</RouteLink> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {published ? <button type="button" className="desk-button-danger-outline" onClick={() => setConfirmUnpublish(true)}>{t`Unpublish`}</button>
            : <button type="button" className="desk-button-primary" disabled={!handle || publication.isPending}
              title={handle ? undefined : t`Claim a handle first.`} onClick={() => { publication.reset(); setConsenting(true); }}>{t`Publish…`}</button>}
          <button type="button" className="desk-button gap-2" onClick={() => setPreviewing(true)}><Eye aria-hidden="true" className="h-4 w-4" />{t`Preview`}</button>
        </div>
        {!handle && !published ? <p className="text-sm text-muted">{t`Claim a handle first.`}</p> : null}
        {publication.error && !consenting ? <p role="alert" className="text-sm text-danger">{fieldError(publication.error, "public_visible")}</p> : null}
      </div>
    </SettingsRow>
    <SettingsRow label={t`What visitors see`} helper={t`Every section starts hidden. Switching one on takes effect straight away.`}>
      <VisibilitySwitches makerspaceId={makerspaceId} flags={profile} />
    </SettingsRow>
    <PublishConsentDialog open={consenting} handle={handle ?? ""} pending={publication.isPending}
      error={publication.error ? fieldError(publication.error, "publication_consent") : undefined}
      onCancel={() => setConsenting(false)} onPublish={publish} />
    <ConfirmDialog open={confirmUnpublish} tone="danger" title={t`Unpublish your profile?`} confirmLabel={t`Unpublish`}
      message={t`Your public page and share card go offline straight away. Publishing again will ask for your consent again.`}
      pending={publication.isPending} onCancel={() => setConfirmUnpublish(false)}
      onConfirm={() => publication.mutate({ public_visible: false }, { onSettled: () => setConfirmUnpublish(false) })} />
    <ProfilePreviewDialog open={previewing} onClose={() => setPreviewing(false)} profile={profile} timeline={timeline.data ?? []} />
  </SettingsSection>;
}
