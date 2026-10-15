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
  const [confirmDisable, setConfirmDisable] = useState(false);
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [challenge, setChallenge] = useState<MfaChallenge>();
  const [codes, setCodes] = useState<string[]>();
  const [notice, setNotice] = useState("");
  useEffect(() => { void refreshAccessToken().then(setReady); }, []);
  const status = useQuery({ queryKey: ["mfa-status"], enabled: ready,
    queryFn: () => staffRequest<{ enabled: boolean; required: boolean }>("/auth/mfa"), retry: false });
  const enroll = useMutation({ mutationFn: () => staffRequest<MfaChallenge>("/auth/mfa", {
    method: "POST", body: JSON.stringify({ password }),
  }), onSuccess: (value) => { clearAccessToken(); setPassword(""); setChallenge(value); } });
  const change = useMutation({ mutationFn: (operation: "recovery" | "disable") => staffRequest<{ recovery_codes?: string[] }>(`/auth/mfa/${operation}`, {
    method: "POST", body: JSON.stringify({ password }),
  }), onSuccess: (value) => { setCodes(value.recovery_codes); setPassword(""); clearAccessToken(); setReady(false); setNotice("Your previous sessions have ended. Sign in again to continue."); } });
  if (challenge) return <MfaFlow challenge={challenge} onCancel={() => { setChallenge(undefined); setReady(false); }}
    onComplete={result => { setAccessToken(result.access); setChallenge(undefined); setReady(true); void status.refetch(); }} />;
  const enabled = status.data?.enabled;
  const busy = enroll.isPending || change.isPending;
  return <>
    <CenteredCardLayout title={codes ? "Save your recovery codes" : "Two-step sign-in"} media={{ icon: "ShieldCheck", tone: "accent" }}
      state={{ status: !ready ? "ready" : status.isLoading ? "loading" : status.error ? "error" : "ready",
        error: "Couldn't load authenticator settings. Try again.", onRetry: () => { void status.refetch(); } }}
      body={codes ? "Each code works once. Save them somewhere secure before you continue." : !ready ? notice || "Sign in to manage your authenticator." :
        `${enabled ? "Your authenticator is enrolled." : "Add an authenticator to protect your account."}${status.data?.required ? " MFA is required for this account." : ""}`}
      content={<div className="grid gap-4">
        {ready ? <><StatusPill label={enabled ? "Authenticator on" : "Authenticator off"} tone={enabled ? "success" : "neutral"} />
          <label className="grid gap-2 text-sm font-semibold" htmlFor="mfa-password">Confirm your current password
            <input id="mfa-password" className="desk-input" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} /></label></> : null}
        {codes ? <MfaRecoveryCodes codes={codes} /> : null}
        {enroll.error || change.error ? <ErrorBlock error={(enroll.error ?? change.error)!} /> : null}
      </div>}
      primary={codes ? { label: "I've saved my codes", onClick: () => { setCodes(undefined); setNotice("Your recovery codes are saved. Sign in again to continue."); } } : !ready ? { label: "Staff sign-in", href: "/admin" } : {
        label: enabled ? "Regenerate recovery codes" : "Enroll authenticator", pending: busy, disabled: !password || status.isLoading,
        disabledReason: "Confirm your current password to continue.", onClick: () => enabled ? change.mutate("recovery") : enroll.mutate() }}
      footer={<div className="grid gap-4"><div className="flex flex-wrap gap-4"><Link to="/admin" className="desk-link min-h-11">Staff sign-in</Link><Link to="/member" className="desk-link min-h-11">Member sign-in</Link></div>
        {ready && enabled && !status.data?.required ? <DangerZone title="Disable MFA" consequence="Your account will use password sign-in without an authenticator."
          action={{ label: "Disable MFA", disabled: !password || busy, onClick: () => setConfirmDisable(true) }} /> : null}</div>} />
    <ConfirmDialog open={confirmDisable} title="Disable MFA?" message="Your account will no longer require an authenticator." confirmLabel="Disable MFA" tone="danger" pending={change.isPending}
      onCancel={() => setConfirmDisable(false)} onConfirm={() => { change.mutate("disable"); setConfirmDisable(false); }} />
  </>;
}
