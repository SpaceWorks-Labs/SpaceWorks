import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { SpaceWorksBadge } from "../../components/SpaceWorksLogo";
import { Card } from "../../components/ui";
import { onMfaEnrollmentRequired } from "../../lib/api/mfaEnrollment";
import { MfaFlow } from "../auth/MfaFlow";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { ChangePasswordGate } from "./ChangePasswordGate";
import { consoleSpaceIds, hasConsoleAccess, isSuperadminUser, mfaGate } from "./consoleAccess";
import { MakerspacePicker } from "./MakerspacePicker";
import { PlatformSignInPanel } from "./PlatformSignInPanel";
import { RecoveryQuarantinePanel } from "./RecoveryQuarantinePanel";
import { StaffAccessDenied } from "./StaffAccessDenied";
import { MfaEnrollmentScreen, MfaGraceBanner, NoStaffRoleScreen } from "./StaffGateScreens";
import { StaffWorkspace } from "./StaffWorkspace";
import { tabFromStaffPath } from "./staffTabs";
import { useConsoleSession } from "./useConsoleSession";

/** A whole-screen status between sign-in and the console: the shell is not up yet, so this owns the landmark. */
function StaffLoading({ message, restoring = false }: { message: string; restoring?: boolean }) {
  return (
    <main id="main-content" className="grid min-h-dvh min-w-0 place-items-center px-4 sm:px-5">
      <Card className={`w-full max-w-md text-sm font-semibold text-muted ${restoring ? "flex flex-col items-center gap-4 p-8 text-center" : "p-6"}`}>
        <SpaceWorksBadge className={restoring ? undefined : "mb-5"} />
        <p role="status">{message}</p>
      </Card>
    </main>
  );
}

/**
 * The staff console. One account per person: a person signs in once and the console opens
 * for the spaces where they hold a staff role or a delegated grant (several spaces: they
 * pick one). The platform superadmin keeps a separate account and sign-in.
 */
export function StaffApp({ guestOnly = false }: { guestOnly?: boolean }) {
  const location = useLocation();
  const session = useConsoleSession(guestOnly);
  const { activeMakerspace, consoleMakerspaces, makerspaces, queryClient, recovery, selected, singleTenantLocked, tenant, user } = session;
  // The shared enrolment handler (#128 C-1): a staff call refused mid-session swaps the console in place.
  const [enrolmentRequired, setEnrolmentRequired] = useState(false);
  useEffect(() => onMfaEnrollmentRequired(() => setEnrolmentRequired(true)), []);
  useEffect(() => { if (user && mfaGate(user) === "none") setEnrolmentRequired(false); }, [user]);
  const memberHref = tenant.mode !== "single" && session.routeMakerspaceSlug ? `/m/${encodeURIComponent(session.routeMakerspaceSlug)}/member` : "/member";
  if (session.restoring) return <StaffLoading message={t`Restoring session...`} restoring />;
  // MfaFlow is a whole page (CenteredCardLayout owns the main landmark and the h1).
  if (session.mfaChallenge) return <MfaFlow key={session.mfaChallenge.challenge} challenge={session.mfaChallenge} onComplete={session.mfaCompleted} onCancel={() => session.setMfaChallenge(undefined)} />;
  if (!user && session.platform) return <PlatformSignInPanel error={session.login.error?.message} isPending={session.login.isPending} onSubmit={session.login.mutate} />;
  if (!user) {
    return <MemberAuthPanel eyebrow={guestOnly ? t`Front desk` : t`Staff console`} makerspaceSlug={session.routeMakerspaceSlug ?? ""}
      onAuthenticated={() => { void session.personAuthenticated(); }}
      footer={<a className="text-sm font-semibold underline" href="/admin?context=platform">{t`Platform administrator? Sign in here`}</a>} />;
  }
  if (user.must_change_password) {
    return <ChangePasswordGate username={user.username} onSignOut={session.signOut} onChanged={() => {
      // Drop any error-cached protected queries so the console opens with fresh data.
      queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
      session.setUser({ ...user, must_change_password: false });
    }} />;
  }
  const isSuperadmin = isSuperadminUser(user);
  if (!isSuperadmin && !hasConsoleAccess(user)) return <NoStaffRoleScreen memberHref={memberHref} onSignOut={session.signOut} />;
  const gate = enrolmentRequired ? "required" : mfaGate(user);
  if (gate === "required") return <MfaEnrollmentScreen memberHref={memberHref} onSignOut={session.signOut} />;
  const routeTab = tabFromStaffPath(location.pathname, guestOnly);
  const globalRoute = routeTab === "organizations" || (isSuperadmin && (routeTab === "platform-dashboard" || routeTab === "platform-spaces"))
    || (!isSuperadmin && consoleSpaceIds(user).size === 0);
  if (isSuperadmin && recovery.data?.mode === "quarantined") {
    return <RecoveryQuarantinePanel state={recovery.data} onAcknowledged={(next) => {
      queryClient.setQueryData(["deployment-recovery-state"], next);
      queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    }} />;
  }
  if (singleTenantLocked && makerspaces.isLoading) return <StaffLoading message={t`Checking makerspace access...`} />;
  if (singleTenantLocked && !activeMakerspace && (isSuperadmin || !consoleSpaceIds(user).has(tenant.makerspaceId ?? -1))) {
    return <StaffAccessDenied makerspaceName={tenant.bootstrap?.makerspace.name} onSignOut={session.signOut} />;
  }
  if (!singleTenantLocked && (session.routeMakerspaceSlug || selected !== null) && makerspaces.isLoading) return <StaffLoading message={t`Opening makerspace...`} />;
  if (!singleTenantLocked && session.routeMakerspace && session.routeMakerspace.id !== selected) return <StaffLoading message={t`Opening makerspace...`} />;
  // The superadmin always picks a space; a person only when several are open to them (a grant-only
  // person whose spaces have no console row goes straight to their granted resources).
  if (!singleTenantLocked && !globalRoute && !activeMakerspace && (isSuperadmin || consoleMakerspaces.length > 1)) {
    return <MakerspacePicker makerspaces={consoleMakerspaces} loading={makerspaces.isLoading} username={user.username}
      person={!isSuperadmin} onSelect={session.chooseMakerspace} onSignOut={session.signOut} />;
  }
  const activeMembership = user.makerspaces.find((item) => item.id === selected);
  // A superadmin holds every action in the space they chose (#115), and none before choosing one.
  const activeActions = isSuperadmin ? (activeMakerspace ? user.superadmin_actions ?? [] : []) : activeMembership?.actions ?? [];
  return <StaffWorkspace activeMakerspace={activeMakerspace} actions={activeActions}
    canConfigureMachineTypes={activeMembership?.can_configure_machine_types ?? isSuperadmin}
    isMachineOnly={activeMembership?.is_machine_only ?? false} guestOnly={guestOnly} isSuperadmin={isSuperadmin}
    makerspaces={isSuperadmin ? makerspaces.data ?? [] : consoleMakerspaces} onAuthRefresh={session.refreshAuthUser} selected={selected}
    setSelected={session.chooseMakerspace} setTab={session.setTab} signOut={session.signOut} singleTenantLocked={singleTenantLocked}
    lockedMakerspaceId={tenant.makerspaceId ?? undefined} user={user}
    notice={gate === "grace" && user.mfa_grace_ends_at ? <MfaGraceBanner endsAt={user.mfa_grace_ends_at} /> : undefined} />;
}
