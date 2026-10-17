import { currentSessionContext } from "../../lib/api/sessionContext";
import { useOptionalTenant } from "../../lib/tenant";
import { reauthenticationSessionKey } from "./reauthenticationApi";
import { PasswordlessMfaProof } from "./PasswordlessMfaProof";
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { clearAccessToken, refreshAccessToken, setAccessToken, staffRequest } from "../../lib/api";
import { CenteredCardLayout } from "../../components/layouts";
import { ConfirmDialog, DangerZone, ErrorBlock, StatusPill } from "../../components/ui";
import { MfaRecoveryCodes } from "./MfaRecoveryCodes";
import { MfaFlow } from "./MfaFlow";
import type { MfaChallenge } from "./mfaApi";

export function MfaAccountPage() {
  const context = currentSessionContext();
  const tenant = useOptionalTenant();
  const signInHref = context.startsWith("staff:") && tenant?.mode !== "single"
    ? `/m/${encodeURIComponent(context.slice(6))}/admin` : context === "member" ? "/member"
    // A single-tenant /admin would resolve to that tenant's staff context; keep platform explicit.
    : context === "platform" ? "/admin?context=platform" : "/admin";
  const [confirmDisable, setConfirmDisable] = useState(false);
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [challenge, setChallenge] = useState<MfaChallenge>();
  const [codes, setCodes] = useState<string[]>();
  const [notice, setNotice] = useState("");
  useEffect(() => { void refreshAccessToken().then(setReady); }, []);
  const status = useQuery({ queryKey: [...reauthenticationSessionKey(), "mfa-status"], enabled: ready,
    queryFn: () => staffRequest<{ available: boolean; enabled: boolean; required: boolean; password_available: boolean }>("/auth/mfa"), retry: false });
  const enroll = useMutation({ mutationFn: () => staffRequest<MfaChallenge>("/auth/mfa", {
    method: "POST", body: JSON.stringify({ password }),
  }), onSuccess: (value) => { clearAccessToken(); setPassword(""); setChallenge(value); } });
  const change = useMutation({ mutationFn: (operation: "recovery" | "disable") => staffRequest<{ recovery_codes?: string[] }>(`/auth/mfa/${operation}`, {
    method: "POST", body: JSON.stringify({ password }),
  }), onSuccess: (value) => { setCodes(value.recovery_codes); setPassword(""); clearAccessToken(); setReady(false); setNotice("Your previous sessions have ended. Sign in again to continue."); } });
  if (challenge) return <MfaFlow challenge={challenge} onCancel={() => { setChallenge(undefined); setReady(false); }}
    onComplete={result => { setAccessToken(result.access); setChallenge(undefined); setReady(true); void status.refetch(); }} />;
  const enabled = status.data?.enabled;
  // The deployment-level MFA switch: while it is off nobody can enroll or regenerate codes, but an
  // already-enrolled account keeps its authenticator and may still disable it.
  const available = status.data?.available !== false;
  const manageable = !!status.data && (available || !!enabled);
  // A passwordless account (social / OIDC sign-in only) cannot type a current password, so
  // enrollment is proven through PasswordlessMfaProof instead; managing an EXISTING
  // authenticator still needs a password the account does not have.
  const passwordAvailable = status.data?.password_available !== false;
  const needsPassword = passwordAvailable || !!enabled;
  const busy = enroll.isPending || change.isPending;
  return <>
    <CenteredCardLayout title={codes ? "Save your recovery codes" : "Two-step sign-in"} media={{ icon: "ShieldCheck", tone: "accent" }}
      state={{ status: !ready ? "ready" : status.isLoading ? "loading" : status.error ? "error" : "ready",
        error: "Couldn't load authenticator settings. Try again.", onRetry: () => { void status.refetch(); } }}
      body={codes ? "Each code works once. Save them somewhere secure before you continue." : !ready ? notice || "Sign in to manage your authenticator." :
        `${!available ? "Two-step sign-in is turned off on this deployment." : enabled ? "Your authenticator is enrolled." : "Add an authenticator to protect your account."}${status.data?.required ? " MFA is required for this account." : ""}`}
      content={<div className="grid gap-4">
        {ready ? <><StatusPill label={enabled ? "Authenticator on" : "Authenticator off"} tone={enabled ? "success" : "neutral"} />
          {!manageable ? null : passwordAvailable ? <label className="grid gap-2 text-sm font-semibold" htmlFor="mfa-password">Confirm your current password
            <input id="mfa-password" className="desk-input" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} /></label>
            : !enabled ? <PasswordlessMfaProof />
            : <p className="text-sm text-muted">Your existing MFA-management operations require a current password. Contact your administrator if you cannot supply one.</p>}</> : null}
        {codes ? <MfaRecoveryCodes codes={codes} /> : null}
        {enroll.error || change.error ? <ErrorBlock error={(enroll.error ?? change.error)!} /> : null}
      </div>}
      primary={codes ? { label: "I've saved my codes", onClick: () => { setCodes(undefined); setNotice("Your recovery codes are saved. Sign in again to continue."); } } : !ready || !available ? { label: "Sign in", href: signInHref } : {
        label: enabled ? "Regenerate recovery codes" : "Enroll authenticator", pending: busy, disabled: (needsPassword && !password) || status.isLoading,
        disabledReason: passwordAvailable ? "Confirm your current password to continue." : "Managing an enrolled authenticator requires a current password.",
        onClick: () => enabled ? change.mutate("recovery") : enroll.mutate() }}
      footer={<div className="grid gap-4"><div className="flex flex-wrap gap-4"><Link to={signInHref} className="inline-flex min-h-11 items-center rounded-control font-semibold text-accent-ink underline underline-offset-4 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">Return to sign-in</Link><Link to="/member" className="inline-flex min-h-11 items-center rounded-control font-semibold text-accent-ink underline underline-offset-4 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">Member sign-in</Link></div>
        {ready && enabled && !status.data?.required ? <DangerZone title="Disable MFA" consequence="Your account will use password sign-in without an authenticator."
          action={{ label: "Disable MFA", disabled: !password || busy, onClick: () => setConfirmDisable(true) }} /> : null}</div>} />
    <ConfirmDialog open={confirmDisable} title="Disable MFA?" message="Your account will no longer require an authenticator." confirmLabel="Disable MFA" tone="danger" pending={change.isPending}
      onCancel={() => setConfirmDisable(false)} onConfirm={() => { change.mutate("disable"); setConfirmDisable(false); }} />
  </>;
}
