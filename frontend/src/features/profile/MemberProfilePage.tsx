import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { SettingsLayout } from "../../components/layouts";
import { refreshAccessToken } from "../../lib/api";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { GlobalProfileEditor } from "./edit/GlobalProfileEditor";
import { useOwnProfile } from "./edit/profileEditApi";

/** /member/profile: the account-level profile editor, reachable without picking a makerspace first. */
export function MemberProfilePage() {
  const [signedIn, setSignedIn] = useState<boolean>();
  useEffect(() => { void refreshAccessToken("person").then(setSignedIn).catch(() => setSignedIn(false)); }, []);
  if (signedIn === false) return <MemberAuthPanel eyebrow={t`Your profile`} onAuthenticated={() => setSignedIn(true)}
    context={<p className="text-sm text-muted">{t`Sign in to edit your profile.`}</p>} />;
  return <SettingsLayout state={{ status: signedIn === undefined ? "loading" : "ready" }}
    header={{ title: t`Your profile`, eyebrow: t`Member area`, subtitle: t`One profile for your whole account, shown across every space you belong to.`,
      secondary: { label: t`Back to member area`, href: "/member" } }}
    sections={[{ id: "profile", rows: signedIn ? <><GlobalProfileEditor /><ProfileLinkHint /></> : null }]} />;
}

function ProfileLinkHint() {
  const profile = useOwnProfile();
  if (!profile.data) return null;
  const href = profile.data.handle ? `/${profile.data.handle}` : `/profiles/by-account/${profile.data.account_id}`;
  return <p className="mt-5 text-sm text-muted"><a className="font-semibold text-accent-ink underline-offset-2 hover:underline" href={href}>{t`View your profile as others see it`}</a></p>;
}
