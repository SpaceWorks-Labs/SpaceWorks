import { t } from "@lingui/core/macro";
type Audience = "members" | "accounts" | "invite" | "participating_organizations";

/** One wording for who may register, shared by events, series and the space default. */
export const AUDIENCE_LABELS: Record<Audience, string> = {
  accounts: t`Anyone with an account`,
  members: t`Our members`,
  participating_organizations: t`Selected organizations`,
  invite: t`Invite only`,
};

export function AudienceOptions({ value, organizationAudienceEnabled }: { value?: string | null; organizationAudienceEnabled: boolean }) {
  return <>
    <option value="accounts">{AUDIENCE_LABELS.accounts}</option>
    <option value="members">{AUDIENCE_LABELS.members}</option>
    {organizationAudienceEnabled || value === "participating_organizations"
      ? <option value="participating_organizations" disabled={!organizationAudienceEnabled}>{AUDIENCE_LABELS.participating_organizations}</option> : null}
    <option value="invite">{AUDIENCE_LABELS.invite}</option>
  </>;
}
