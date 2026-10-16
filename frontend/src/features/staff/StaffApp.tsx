import { SpaceWorksBadge } from "../../components/SpaceWorksLogo";
import { Card } from "../../components/ui";
import { ChangePasswordGate } from "./ChangePasswordGate";
import { LoginPanel } from "./LoginPanel";
import { MfaFlow } from "../auth/MfaFlow";
import { MakerspacePicker } from "./MakerspacePicker";
import { StaffAccessDenied } from "./StaffAccessDenied";
import { StaffWorkspace } from "./StaffWorkspace";
import { RecoveryQuarantinePanel } from "./RecoveryQuarantinePanel";
import { useStaffSession } from "./useStaffSession";
import { tabFromStaffPath } from "./staffTabs";
import { useLocation } from "react-router-dom";

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

export function StaffApp({ guestOnly = false }: { guestOnly?: boolean }) {
  const location = useLocation();
  const {
    activeMakerspace,
    chooseMakerspace,
    login,
    mfaChallenge,
    setMfaChallenge,
    mfaCompleted,
    makerspaces,
    queryClient,
    recovery,
    refreshAuthUser,
    restoring,
    routeMakerspace,
    routeMakerspaceSlug,
    selected,
    setTab,
    setUser,
    signOut,
    singleTenantLocked,
    socialLoginSucceeded,
    tenant,
    user,
  } = useStaffSession(guestOnly);
  if (restoring) {
    return <StaffLoading message="Restoring session..." restoring />;
  }

  // MfaFlow is a whole page (CenteredCardLayout owns the main landmark and the h1).
  if (mfaChallenge) return <MfaFlow key={mfaChallenge.challenge} challenge={mfaChallenge} onComplete={mfaCompleted} onCancel={() => setMfaChallenge(undefined)} />;

  if (!user) {
    return (
      <LoginPanel
        error={login.error?.message}
        guestOnly={guestOnly}
        isPending={login.isPending}
        onSubmit={login.mutate}
        onSocialSuccess={socialLoginSucceeded}
      />
    );
  }

  if (user.must_change_password) {
    return (
      <ChangePasswordGate
        username={user.username}
        onChanged={() => {
          // Clear the gate AND drop any error-cached protected queries so the
          // console opens with fresh data instead of a stale 403.
          queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
          setUser({ ...user, must_change_password: false });
        }}
        onSignOut={signOut}
      />
    );
  }

  const isSuperadmin = user.is_superuser || user.role === "superadmin";
  const routeTab = tabFromStaffPath(location.pathname, guestOnly);
  const globalRoute = routeTab === "organizations" || (isSuperadmin && routeTab === "platform-dashboard");

  if (isSuperadmin && recovery.data?.mode === "quarantined") {
    return (
      <RecoveryQuarantinePanel
        state={recovery.data}
        onAcknowledged={(next) => {
          queryClient.setQueryData(["deployment-recovery-state"], next);
          queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
        }}
      />
    );
  }

  if (singleTenantLocked && makerspaces.isLoading) {
    return <StaffLoading message="Checking makerspace access..." />;
  }

  const hasSingleTenantAccess =
    !singleTenantLocked || Boolean(activeMakerspace) || Boolean(user.event_grants?.some((grant) => grant.makerspace_id === tenant.makerspaceId) || user.booking_grants?.some((grant) => grant.makerspace_id === tenant.makerspaceId));

  if (!hasSingleTenantAccess) {
    return (
      <StaffAccessDenied
        makerspaceName={tenant.bootstrap?.makerspace.name}
        onSignOut={signOut}
      />
    );
  }

  if (!singleTenantLocked && routeMakerspaceSlug && makerspaces.isLoading) {
    return <StaffLoading message="Opening makerspace..." />;
  }

  if (!singleTenantLocked && routeMakerspace && routeMakerspace.id !== selected) {
    return <StaffLoading message="Opening makerspace..." />;
  }

  if (!singleTenantLocked && selected !== null && makerspaces.isLoading) {
    return <StaffLoading message="Restoring makerspace..." />;
  }

  if (!singleTenantLocked && isSuperadmin && selected !== null && !activeMakerspace && !globalRoute) {
    return (
      <MakerspacePicker
        makerspaces={makerspaces.data ?? []}
        loading={makerspaces.isLoading}
        username={user.username}
        onSelect={chooseMakerspace}
        onSignOut={signOut}
      />
    );
  }

  if (!singleTenantLocked && isSuperadmin && selected === null && !globalRoute) {
    return (
      <MakerspacePicker
        makerspaces={makerspaces.data ?? []}
        loading={makerspaces.isLoading}
        username={user.username}
        onSelect={chooseMakerspace}
        onSignOut={signOut}
      />
    );
  }

  const activeMembership = user.makerspaces.find((item) => item.id === selected);
  const activeActions = activeMembership?.actions ?? [];
  const makerspaceList = makerspaces.data ?? [];

  return (
    <StaffWorkspace
      activeMakerspace={activeMakerspace}
      actions={activeActions}
      canConfigureMachineTypes={activeMembership?.can_configure_machine_types ?? isSuperadmin}
      isMachineOnly={activeMembership?.is_machine_only ?? false}
      guestOnly={guestOnly}
      isSuperadmin={isSuperadmin}
      makerspaces={makerspaceList}
      onAuthRefresh={refreshAuthUser}
      selected={selected}
      setSelected={chooseMakerspace}
      setTab={setTab}
      signOut={signOut}
      singleTenantLocked={singleTenantLocked}
      lockedMakerspaceId={tenant.makerspaceId ?? undefined}
      user={user}
    />
  );
}
