import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { MailCheck } from "lucide-react";
import { authErrorMessage } from "../../lib/api/authErrorCopy";
import { tokenHeaders, useTurnstileGate } from "../../components/auth/useTurnstileGate";
import { resendLoginCode } from "./mfaApi";

/**
 * "Send a new code" for an emailed sign-in code, with how many resends are left (S-B allows
 * two). Resending is a CAPTCHA route, so a `captcha_required` answer shows the check and
 * resends with its token.
 */
export function MfaEmailCodeResend({ challenge, initialResends = 2, turnstileSiteKey }: {
  challenge: string; initialResends?: number; turnstileSiteKey?: string;
}) {
  const [left, setLeft] = useState(initialResends);
  const [notice, setNotice] = useState("");
  const resend = useMutation({
    mutationFn: (token?: string) => resendLoginCode(challenge, tokenHeaders(token)),
    onSuccess: result => {
      const next = result.resends_left;
      setLeft(next);
      setNotice(`We sent a new code. ${next === 0 ? "That was the last resend." : `${next} ${next === 1 ? "resend" : "resends"} left.`}`);
      captcha.reset();
    },
    onError: error => { if (!captcha.catchError(error)) setNotice(""); },
  });
  const captcha = useTurnstileGate(turnstileSiteKey, token => resend.mutate(token));
  const error = resend.error && !captcha.slot ? authErrorMessage(resend.error, "Couldn't send a new code. Try again.") : "";
  return <div className="grid gap-3">
    <button type="button" className="desk-button min-h-11 gap-2" disabled={left <= 0 || resend.isPending}
      aria-describedby="mfa-resend-left" onClick={() => resend.mutate(undefined)}>
      <MailCheck aria-hidden="true" size={20} />{resend.isPending ? "Sending…" : "Send a new code"}
    </button>
    <p id="mfa-resend-left" className="text-sm text-muted">
      {left > 0 ? `${left} ${left === 1 ? "resend" : "resends"} left.` : "No resends left. Restart sign-in to get a new code."}</p>
    {captcha.slot}
    <p role="status" aria-live="polite" className="text-sm text-ink empty:hidden">{notice}</p>
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
  </div>;
}
