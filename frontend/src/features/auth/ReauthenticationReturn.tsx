import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { confirmEnrollmentEmail } from "./reauthenticationApi";
import { refreshAccessToken } from "../../lib/api";

export function ReauthenticationReturn({ confirmation }: { confirmation: boolean }) {
  const [token] = useState(() => {
    if (!confirmation) return "";
    const raw = new URLSearchParams(window.location.hash.replace(/^#/, "")).get("token") || "";
    window.history.replaceState({}, "", window.location.pathname);
    return raw;
  });
  const confirm = useMutation({ mutationFn: async () => {
    if (!await refreshAccessToken()) throw new Error("Open this link in the same signed-in browser session that requested it.");
    return confirmEnrollmentEmail(token);
  } });
  return <main className="desk-shell p-6"><section className="desk-panel mx-auto max-w-lg space-y-4 p-6">
    <h1 className="title-page">{confirmation ? "Confirm authenticator enrollment" : "Identity provider returned"}</h1>
    {!confirmation ? <p>Return to the browser window that opened this page.</p> : <>
      <p>This link works once, in the same browser session that requested it.</p>
      <button className="desk-button-primary" disabled={!token || confirm.isPending || confirm.isSuccess} onClick={() => confirm.mutate()}>{confirm.isPending ? "Confirming..." : "Confirm enrollment"}</button>
      {confirm.isSuccess ? <><p>Confirmed. Continue to enroll your authenticator.</p><a className="desk-link" href="/mfa">Enroll authenticator</a></> : null}
      {confirm.error ? <p role="alert" className="text-danger">{confirm.error.message}</p> : null}
    </>}
  </section></main>;
}
