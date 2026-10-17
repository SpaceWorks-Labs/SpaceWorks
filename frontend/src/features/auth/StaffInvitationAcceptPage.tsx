import { useOptionalTenant } from "../../lib/tenant";
import { useState } from "react";
import { CenteredCardLayout } from "../../components/layouts";
import { PasswordInput } from "./PasswordInput";
import { useMutation } from "@tanstack/react-query";

import { mfaRequest } from "./mfaApi";

export function StaffInvitationAcceptPage() {
  const tenant = useOptionalTenant();
  const [link] = useState(() => new URLSearchParams(window.location.hash.slice(1)));
  const [password, setPassword] = useState("");
  const accept = useMutation({ mutationFn: () => mfaRequest<{ detail: string }>("/auth/staff-invitations/accept", {
    token: link.get("token"), makerspace_slug: link.get("space"), password,
  }), onSuccess: () => { setPassword(""); window.history.replaceState(null, "", window.location.pathname); } });
  return <CenteredCardLayout width={480} state={{ status: "ready" }}
    media={{ avatars: [{ kind: "icon", icon: "Building2", tone: "accent" }, { kind: "icon", icon: "User", tone: "info" }] }}
    title={accept.data ? "You're in" : "Accept your staff invitation"}
    body={accept.data ? <p role="status">{accept.data.detail}</p> : "You've been invited to join a makerspace on Space Works. This link works once."}
    primary={accept.data ? { label: "Sign in with your email", href: tenant?.mode !== "single" && link.get("space") ? `/m/${encodeURIComponent(link.get("space")!)}/admin` : "/admin" } : {
      label: "Accept invitation", pending: accept.isPending, disabled: !link.get("token"),
      disabledReason: "Open the complete invitation link from your email.",
      onClick: () => (document.getElementById("staff-invitation-form") as HTMLFormElement)?.requestSubmit(),
    }}
    footer={!accept.data ? "Choose the initial password for the separate staff account your administrator created. Your member account stays unchanged." : undefined}
    content={!accept.data ? <form id="staff-invitation-form" className="grid gap-3" onSubmit={(event) => { event.preventDefault(); if (!accept.isPending) accept.mutate(); }}>
      <label className="text-sm font-semibold" htmlFor="invite-password">Password</label>
      <PasswordInput id="invite-password" autoComplete="new-password" value={password} required onChange={(event) => setPassword(event.target.value)} />
      {accept.error ? <p role="alert" className="text-danger">{accept.error.message}</p> : null}
    <button type="submit" disabled={accept.isPending} hidden aria-hidden="true" tabIndex={-1} />
    </form> : undefined} />;
}
