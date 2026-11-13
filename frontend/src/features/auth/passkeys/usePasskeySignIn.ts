import { useCallback, useEffect, useRef, useState } from "react";
import { WebAuthnAbortService } from "@simplewebauthn/browser";
import type { PasskeyLogin } from "../../../generated/api";
import { authErrorMessage } from "../../../lib/api/authErrorCopy";
import { finishPasskeySignIn, passkeySignInOptions } from "./passkeyApi";
import { PasskeyDeviceError, isPasskeyCancelled, passkeyAutofillSupported, passkeysSupported } from "./webauthn";

/**
 * Passwordless sign-in with a passkey (S-A's discoverable-credential routes).
 *
 * - `enabled` is `/api/v1/config`'s `passkeys_enabled` (and the screen being a sign-in form).
 * - When the browser supports conditional UI, the passkey is offered in the email field's
 *   autofill list (the field needs `autocomplete="username webauthn"`); no prompt opens by itself,
 *   and a failure to prepare it stays silent (the button and the password still work).
 * - `signIn()` is the explicit button. It replaces any waiting autofill request.
 * - A browser without WebAuthn gets `supported: false`, and the caller shows no passkey control.
 */
export function usePasskeySignIn({ enabled, onSignedIn }: { enabled: boolean; onSignedIn: (result: PasskeyLogin) => void }) {
  const supported = enabled && passkeysSupported();
  const [autofill, setAutofill] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const done = useRef(onSignedIn);
  done.current = onSignedIn;
  const run = useCallback(async (conditional: boolean) => {
    if (!conditional) { setPending(true); setError(""); }
    try {
      const ceremony = await passkeySignInOptions().catch(failure => {
        if (conditional) throw new DOMException("Autofill unavailable.", "AbortError");
        throw failure;
      });
      done.current(await finishPasskeySignIn(ceremony, conditional));
    } catch (failure) {
      // The waiting autofill request is a convenience: a device that cannot run it stays silent, as documented above.
      const quiet = isPasskeyCancelled(failure) || (failure instanceof DOMException && failure.name === "AbortError")
        || (conditional && failure instanceof PasskeyDeviceError);
      if (!quiet) setError(authErrorMessage(failure, "That passkey didn't work. Try again."));
    } finally {
      if (!conditional) setPending(false);
    }
  }, []);
  useEffect(() => {
    if (!supported) return;
    let active = true;
    void passkeyAutofillSupported().then(ok => {
      if (!active || !ok) return;
      setAutofill(true);
      void run(true);
    });
    return () => { active = false; WebAuthnAbortService.cancelCeremony(); };
  }, [supported, run]);
  return { supported, autofill, pending, error, signIn: () => void run(false) };
}
