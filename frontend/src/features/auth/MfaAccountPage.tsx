import { t } from "@lingui/core/macro";
import { currentSessionContext } from "../../lib/api/sessionContext";
import { useOptionalTenant } from "../../lib/tenant";
import { reauthenticationSessionKey } from "./reauthenticationApi";
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { clearAccessToken, refreshAccessToken, setAccessToken, staffRequest } from "../../lib/api";
import { CenteredCardLayout, SettingsLayout } from "../../components/layouts";
import { ErrorBlock } from "../../components/ui";
import { HelpLink } from "../help/HelpLink";
import { MfaAuthenticatorSection, type MfaStatus } from "./MfaAuthenticatorSection";
import { MfaRecoveryCodes } from "./MfaRecoveryCodes";
import { MfaFlow } from "./MfaFlow";
import type { MfaChallenge } from "./mfaApi";
import { KnownDevicesList } from "./KnownDevicesList";
import { LinkedSignInList } from "./LinkedSignInList";
import { PasskeyList } from "./passkeys/PasskeyList";
import { listPasskeys } from "./passkeys/passkeyApi";
import { passkeysKey } from "./securityQueries";
import { SignOutEverywhere } from "./SignOutEverywhere";

const linkClass = "inline-flex min-h-11 items-center rounded-control font-semibold text-accent-ink underline underline-offset-4 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

/**
 * The account security page (`/mfa`): the authenticator app, passkeys, remembered devices and
 * "sign out everywhere". Passkeys and devices belong to a person's own account, so the platform
 * superadmin sees the authenticator and sessions only.
 */
export function MfaAccountPage() {
  const context = currentSessionContext();
  const person = context === "person";
  const tenant = useOptionalTenant();
  // One account per person (U-B): a staff console may send people here with ?return= to
  // come back after enrolling; otherwise a person returns to their account.
  const back = new URLSearchParams(window.location.search).get("return");
  const returnHref = back && back.startsWith("/") && !back.startsWith("//") ? back : null;
  const signInHref = context === "platform" ? "/admin?context=platform"
    : returnHref ?? (tenant?.mode === "single" ? "/member/account" : "/member");
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [challenge, setChallenge] = useState<MfaChallenge>();
  const [codes, setCodes] = useState<string[]>();
  const [notice, setNotice] = useState("");
  useEffect(() => { void refreshAccessToken().then(setReady); }, []);
  const status = useQuery({ queryKey: [...reauthenticationSessionKey(), "mfa-status"], enabled: ready,
    queryFn: () => staffRequest<MfaStatus>("/auth/mfa"), retry: false });
  const passkeys = useQuery({ queryKey: passkeysKey, queryFn: listPasskeys, enabled: ready && person, retry: false });
  const signedOut = (message: string) => { clearAccessToken(); setReady(false); setNotice(message); };
  const enroll = useMutation({ mutationFn: () => staffRequest<MfaChallenge>("/auth/mfa", {
    method: "POST", body: JSON.stringify({ password }),
  }), onSuccess: (value) => { clearAccessToken(); setPassword(""); setChallenge(value); } });
  const change = useMutation({ mutationFn: (operation: "recovery" | "disable") => staffRequest<{ recovery_codes?: string[] }>(`/auth/mfa/${operation}`, {
    method: "POST", body: JSON.stringify({ password }),
  }), onSuccess: (value) => { setCodes(value.recovery_codes); setPassword(""); signedOut("Your previous sessions have ended. Sign in again to continue."); } });
  if (challenge) return <MfaFlow challenge={challenge} onCancel={() => { setChallenge(undefined); setReady(false); }}
    onComplete={result => { setAccessToken(result.access); setChallenge(undefined); setReady(true); void status.refetch(); }} />;
  const links = <div className="flex flex-wrap gap-4"><Link to={signInHref} className={linkClass}>{ready && returnHref ? t`Back to where you were` : t`Return to sign-in`}</Link>
    <Link to="/member" className={linkClass}>{t`Member sign-in`}</Link></div>;
  if (codes || !ready || status.error) {
    return <CenteredCardLayout title={codes ? t`Save your recovery codes` : t`Two-step sign-in`} media={{ icon: "ShieldCheck", tone: "accent" }}
      state={status.error && ready ? { status: "error", error: t`Couldn't load authenticator settings. Try again.`, onRetry: () => { void status.refetch(); } } : { status: "ready" }}
      body={codes ? t`Each code works once. Save them somewhere secure before you continue.` : notice || t`Sign in to manage your authenticator.`}
      content={codes ? <MfaRecoveryCodes codes={codes} /> : undefined}
      primary={codes ? { label: t`I've saved my codes`, onClick: () => { setCodes(undefined); setNotice(ready ? "" : t`Your recovery codes are saved. Sign in again to continue.`); } }
        : { label: t`Sign in`, href: signInHref }}
      footer={links} />;
  }
  const data = status.data;
  const hasPasskey = (passkeys.data?.passkeys.length ?? 0) > 0;
  const busy = enroll.isPending || change.isPending;
  // Staff enrol here (the console sends them with ?return=); the guide's two-step article covers staff too.
  const helpSpace = tenant?.mode === "single" ? { slug: tenant.slug, enabled_features: tenant.bootstrap?.features ?? [] } : undefined;
  return <SettingsLayout standalone state={status.isLoading || !data ? { status: "loading" } : { status: "ready" }}
    header={{ title: t`Account security`, subtitle: person ? t`Two-step sign-in, passkeys and the devices you sign in from.` : t`Two-step sign-in for the platform account.`,
      meta: <HelpLink article="member/two-step-sign-in" makerspace={helpSpace} singleTenant platform={context === "platform"} className="-ml-2" /> }}
    sections={[
      { id: "two-step", title: t`Authenticator app`, rows: data ? <div className="grid gap-4">
        <MfaAuthenticatorSection status={data} hasPasskey={hasPasskey} passkeysOffered={person && passkeys.data?.passkeys_allowed !== false}
          password={password} setPassword={setPassword} busy={busy} onEnroll={() => enroll.mutate()} onRegenerate={() => change.mutate("recovery")} />
        {enroll.error || change.error ? <ErrorBlock error={(enroll.error ?? change.error)!} /> : null}
      </div> : null },
      ...(person ? [
        { id: "passkeys", title: t`Passkeys`, rows: <PasskeyList onRecoveryCodes={setCodes} onSignedOut={() => signedOut("You removed the passkey this browser signed in with. Sign in again to continue.")} /> },
        { id: "devices", title: t`Remembered devices`, rows: <KnownDevicesList /> },
        { id: "linked", title: t`Linked sign-in accounts`, rows: <LinkedSignInList /> },
      ] : []),
      { id: "sessions", title: t`Sessions`, rows: <div className="grid gap-4">
        <SignOutEverywhere signInHref={person ? "/member/account" : signInHref} onSignedOut={() => setReady(false)} />{links}</div> },
    ]}
    danger={data?.enabled && (!data.required || hasPasskey) ? [{ title: t`Disable MFA`, consequence: "Your account will use password sign-in without an authenticator.",
      action: { label: t`Disable MFA`, disabled: !password || busy, disabledReason: "Confirm your current password to continue.",
        confirm: { title: t`Disable MFA?`, message: t`Your account will no longer require an authenticator.`, confirmLabel: t`Disable MFA` },
        onClick: () => change.mutate("disable") } }] : []} />;
}
