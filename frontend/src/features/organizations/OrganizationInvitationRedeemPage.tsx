import { t } from "@lingui/core/macro";
import { useEffect, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { CenteredCardLayout } from "../../components/layouts";
import {
  fetchMe,
  refreshAccessToken,
  setAccessToken,
  staffRequest,
  type PasswordLoginResponse,
  type StaffAuthUser,
} from "../../lib/api";
import { eligibilityMessage } from "../../lib/eligibilityCopy";

type RedeemResponse = import("../../generated/api").OrganizationInvitationRedeemed;

export function OrganizationInvitationRedeemPage() {
  const { token = "" } = useParams();
  const [user, setUser] = useState<StaffAuthUser | null>(null);
  const [restoring, setRestoring] = useState(true);
  const [credentials, setCredentials] = useState({ username: "", password: "" });
  const redeem = useMutation({
    mutationFn: () => staffRequest<RedeemResponse>("/auth/organization-invitations/redeem/", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  });
  const login = useMutation({
    mutationFn: () => staffRequest<PasswordLoginResponse<StaffAuthUser>>("/auth/login", {
      method: "POST",
      credentials: "include",
      body: JSON.stringify({ ...credentials, surface: "member" }),
    }),
    onSuccess: (response) => {
      setAccessToken(response.access);
      setUser(response.user);
    },
  });

  useEffect(() => {
    let active = true;
    refreshAccessToken()
      .then((refreshed) => refreshed ? fetchMe() : null)
      .then((current) => { if (active && current) setUser(current); })
      .finally(() => { if (active) setRestoring(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (user && token && !redeem.isPending && !redeem.isSuccess && !redeem.isError) {
      redeem.mutate();
    }
  }, [user, token, redeem]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!login.isPending) login.mutate();
  }

  return <CenteredCardLayout width={480} state={{ status: restoring || redeem.isPending ? "loading" : "ready" }}
    media={{ banner: redeem.isSuccess ? "success" : "accent" }} eyebrow={t`Organization invitation`}
    title={redeem.isSuccess ? t`You're in` : t`Join an organization`}
    body={redeem.isSuccess ? t`Your organization access is active. Makerspace actions remain scoped to the organization's linked makerspaces.`
      : redeem.isError ? eligibilityMessage(redeem.error) ?? redeem.error.message : t`You've been invited to join. Sign in to bind this single-use invitation to your account. This link works once.`}
    primary={redeem.isSuccess ? { label: t`Open organizations`, href: "/admin/organizations" }
      : redeem.isError ? { label: t`Return to directory`, href: "/" } : {
        label: t`Sign in and continue`, pending: login.isPending,
        onClick: () => (document.getElementById("organization-invite-form") as HTMLFormElement)?.requestSubmit(),
      }}
    content={!restoring && !user ? <form id="organization-invite-form" className="grid gap-4" onSubmit={submit}>
      <label className="grid gap-2 text-sm font-semibold">{t`Username or email`}<input className="desk-input" autoComplete="username" required value={credentials.username} onChange={(event) => setCredentials({ ...credentials, username: event.target.value })} /></label>
      <label className="grid gap-2 text-sm font-semibold">{t`Password`}<input className="desk-input" type="password" autoComplete="current-password" required value={credentials.password} onChange={(event) => setCredentials({ ...credentials, password: event.target.value })} /></label>
      {login.error ? <p className="text-sm text-danger" role="alert">{login.error.message}</p> : null}
    <button type="submit" disabled={login.isPending} hidden aria-hidden="true" tabIndex={-1} />
    </form> : undefined} />;
}
