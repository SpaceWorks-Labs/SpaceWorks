import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CenteredCardLayout } from "../../components/layouts";
import { logout, memberRequest, refreshAccessToken } from "../../lib/api";
import { StructuredApiError } from "../../lib/api/errors";
import { useOptionalTenant } from "../../lib/tenant";
import { MemberAuthPanel } from "../members/MemberAuthPanel";

type AcceptResult = { detail: string; challenge_required: boolean; makerspace?: { id: number; slug: string; name: string } };

const COPY: Record<string, string> = {
  invite_email_mismatch: t`This invitation was sent to a different email address. Sign out and sign in with that account.`,
  proof_failed: t`That code is not right or has expired. Check it, or ask for a new one.`,
  already_staff: t`You already have a staff role in this makerspace.`,
  tenant_gated: t`This makerspace is temporarily read-only. Try again later.`,
};
const message = (error: unknown) => error instanceof StructuredApiError && error.code && COPY[error.code]
  ? COPY[error.code] : error instanceof Error ? error.message : "Something went wrong. Try again.";

/**
 * Accept a staff-role invitation (one account per person): signed in to your own account
 * whose email is the invited address, then confirm a fresh code emailed to it. Nothing is
 * created until the code is confirmed, and the invitation never creates an account.
 */
export function StaffInvitationAcceptPage() {
  const tenant = useOptionalTenant();
  const client = useQueryClient();
  const [link] = useState(() => new URLSearchParams(window.location.hash.slice(1)));
  const [signedIn, setSignedIn] = useState<boolean>();
  const [code, setCode] = useState("");
  useEffect(() => { void refreshAccessToken("person").then(setSignedIn).catch(() => setSignedIn(false)); }, []);
  const body = { token: link.get("token"), makerspace_slug: link.get("space") };
  const send = useMutation({ mutationFn: () => memberRequest<AcceptResult>("/auth/staff-invitations/accept", {
    method: "POST", body: JSON.stringify(body) }) });
  const confirm = useMutation({ mutationFn: () => memberRequest<AcceptResult>("/auth/staff-invitations/accept", {
    method: "POST", body: JSON.stringify({ ...body, code }) }),
    onSuccess: () => { setCode(""); window.history.replaceState(null, "", window.location.pathname);
      void client.invalidateQueries({ queryKey: ["staff", "me"] }); } });
  const space = confirm.data?.makerspace?.slug ?? link.get("space");
  const consoleHref = tenant?.mode !== "single" && space ? `/m/${encodeURIComponent(space)}/admin` : "/admin";
  if (signedIn === false) {
    return <MemberAuthPanel eyebrow={t`Staff invitation`} makerspaceSlug={link.get("space") ?? ""}
      context={<p className="text-sm text-muted">{t`Sign in with the account that uses the invited email address, or create one with it. Then we'll email you a code to confirm.`}</p>}
      onAuthenticated={() => setSignedIn(true)} />;
  }
  const done = confirm.data && !confirm.data.challenge_required;
  const error = send.error ?? confirm.error;
  const mismatch = error instanceof StructuredApiError && error.code === "invite_email_mismatch";
  const signOut = () => { void logout("person").catch(() => undefined).finally(() => { client.clear(); setSignedIn(false); send.reset(); }); };
  return <CenteredCardLayout width={480} state={{ status: signedIn === undefined ? "loading" : "ready" }}
    media={{ avatars: [{ kind: "icon", icon: "Building2", tone: "accent" }, { kind: "icon", icon: "ShieldCheck", tone: "info" }] }}
    title={done ? t`You're on the team` : t`Accept your staff invitation`}
    body={done ? <p role="status">{t`${confirm.data!.detail} Staff screens need two-step sign-in within three days.`}</p>
      : send.data ? "We emailed a 6-digit code to the invitation address. Enter it to accept."
      : "The staff role is added to the account you're signed in to. We'll email a code to the invited address to confirm it's yours."}
    primary={done ? { label: t`Open the staff console`, href: consoleHref }
      : mismatch ? { label: t`Sign out and use another account`, onClick: signOut }
      : !send.data ? { label: t`Email me a code`, pending: send.isPending, disabled: !link.get("token") || !link.get("space"),
        disabledReason: "Open the complete invitation link from your email.", onClick: () => send.mutate() }
      : { label: t`Accept invitation`, pending: confirm.isPending, disabled: !/^\d{6}$/.test(code),
        disabledReason: "Enter the 6-digit code from the email.", onClick: () => confirm.mutate() }}
    escape={send.data && !done ? { label: t`Send a new code`, disabled: send.isPending, onClick: () => send.mutate() } : undefined}
    content={<div className="grid gap-3">
      {send.data && !done ? <label className="grid gap-2 text-sm font-semibold" htmlFor="invite-code">6-digit code
        <input id="invite-code" className="desk-input w-full" autoComplete="one-time-code" inputMode="numeric" maxLength={6}
          value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} />
      </label> : null}
      {error ? <p role="alert" className="text-sm text-danger">{message(error)}</p> : null}
    </div>} />;
}
