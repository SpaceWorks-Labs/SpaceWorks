import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { refreshAccessToken, StructuredApiError } from "../../lib/api";
import { CenteredCardLayout } from "../../components/layouts";
import { NotFoundPage } from "../NotFoundPage";
import { isProfileMissing, isSignedOutError, useAccountProfile } from "./publicProfileApi";
import { ProfileFrame } from "./PublicProfilePage";
import { useProfileEditorHref } from "./useProfileEditorHref";
import { GlobalProfileView } from "./view/GlobalProfileView";

/** /profiles/by-account/:accountId: how a member without a handle is reached. Signed-in only; unreadable is the shared 404. */
export function ProfileByAccountPage() {
  const { accountId = "" } = useParams();
  const [session, setSession] = useState<"checking" | "in" | "out">("checking");
  useEffect(() => { void refreshAccessToken("person").then(ok => setSession(ok ? "in" : "out")).catch(() => setSession("out")); }, []);
  const profile = useAccountProfile(accountId, session === "in");
  const editor = useProfileEditorHref(profile.data?.audience === "owner");
  if (!/^\d+$/.test(accountId) || isProfileMissing(profile.error)) return <NotFoundPage />;
  if (session === "out" || isSignedOutError(profile.error)) return <CenteredCardLayout state={{ status: "ready" }} title={t`Sign in to view this profile`}
    body={t`This profile is only shown to signed-in members.`} primary={{ label: t`Sign in`, href: "/member" }} />;
  const failure = profile.error instanceof StructuredApiError && profile.error.detail ? profile.error.detail : t`Couldn't load this profile. Try again.`;
  return <ProfileFrame state={session === "checking" || profile.isLoading ? { status: "loading" }
    : profile.error ? { status: "error", error: failure, onRetry: () => { void profile.refetch(); } } : { status: "ready" }}>
    {profile.data ? <GlobalProfileView key={profile.data.account_id} profile={profile.data} editHref={editor.href} /> : null}
  </ProfileFrame>;
}
