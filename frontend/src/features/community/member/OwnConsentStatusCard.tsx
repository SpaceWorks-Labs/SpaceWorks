import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { StatusPill } from "../../../components/ui";
import { formatDate } from "../../../lib/format";
import { communityKeys, communityMemberApi, type OwnConsentStatus } from "../api";

const STATE: Record<Exclude<OwnConsentStatus["state"], "not_applicable">, () => { label: string; tone: "success" | "warn"; help: string }> = {
  current: () => ({ label: t`Consent on file`, tone: "success", help: t`Your parent or guardian's consent is current.` }),
  pending: () => ({ label: t`Waiting for your guardian`, tone: "warn",
    help: t`Your parent or guardian needs to sign the consent before you can take part. Ask them to sign in and open this page, or ask staff at the desk.` }),
  expired: () => ({ label: t`Consent needs renewing`, tone: "warn",
    help: t`Your guardian's consent has ended or the space updated its consent text. Ask them to sign again.` }),
  terms_missing: () => ({ label: t`Not ready yet`, tone: "warn",
    help: t`The space has not published its consent text yet. Ask space staff.` }),
};

/**
 * Open item A27 (PE7): a minor sees their own guardian-consent standing. Renders nothing for anyone
 * the space does not treat as a minor, when loading fails, or when the feature is off (404).
 */
export function OwnConsentStatusCard({ makerspaceId }: { makerspaceId: number }) {
  const status = useQuery({ queryKey: communityKeys.ownConsent(makerspaceId), queryFn: () => communityMemberApi.ownConsent(makerspaceId), retry: false });
  if (status.isLoading) return <LogoLoader label={t`Checking your guardian consent…`} size={48} className="min-h-16 py-3" />;
  const data = status.data;
  if (status.isError || !data?.applies) return null;
  const state = data.state;
  if (state === "not_applicable") return null;
  const shown = STATE[state]();
  const rules = [
    data.guardian_must_be_present ? t`A guardian must be with you when you visit; staff check you in at the desk.` : null,
    data.may_borrow ? null : t`You can't borrow items here yet.`,
    data.may_use_machines ? null : t`You can't use machines here yet.`,
  ].filter((rule): rule is string => Boolean(rule));
  return <section aria-labelledby="own-consent-title" className={`desk-panel grid gap-3 p-5 ${shown.tone === "success" ? "border-success" : "border-warn"}`}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 id="own-consent-title" className="title-panel">{t`Your guardian consent`}</h2>
      <StatusPill label={shown.label} tone={shown.tone} />
    </div>
    <p className="text-sm text-muted">{shown.help}</p>
    {data.state === "current" && data.valid_until ? <p className="text-sm">{t`Valid until ${formatDate(data.valid_until)}`}</p> : null}
    {data.state !== "current" && !data.guardian_named ? <p className="text-sm text-muted">{t`No guardian is on record yet. Ask staff to add your parent or guardian.`}</p> : null}
    {rules.length ? <ul className="grid gap-1 text-sm text-muted">{rules.map(rule => <li key={rule}>{rule}</li>)}</ul> : null}
  </section>;
}
