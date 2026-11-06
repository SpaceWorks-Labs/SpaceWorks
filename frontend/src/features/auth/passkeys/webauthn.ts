/**
 * The browser half of a passkey ceremony, through @simplewebauthn/browser (MIT, no deps).
 * The server's options arrive as JSON and the browser's answer goes back as JSON; nothing
 * here keeps a credential. The browser's own sheet is the only passkey prompt (no custom UI).
 */
import { t } from "@lingui/core/macro";
import {
  WebAuthnError, browserSupportsWebAuthn, browserSupportsWebAuthnAutofill, startAuthentication, startRegistration,
  type PublicKeyCredentialCreationOptionsJSON, type PublicKeyCredentialRequestOptionsJSON,
} from "@simplewebauthn/browser";

/** The person closed the browser's sheet, or another ceremony replaced this one: say nothing. */
export class PasskeyCancelled extends Error {
  constructor() { super("Passkey request cancelled."); this.name = "PasskeyCancelled"; }
}

export function passkeysSupported() {
  try { return browserSupportsWebAuthn(); } catch { return false; }
}

/** Conditional UI: passkeys offered in the email field's autofill list. */
export async function passkeyAutofillSupported() {
  try { return passkeysSupported() && await browserSupportsWebAuthnAutofill(); } catch { return false; }
}

function translate(error: unknown): Error {
  const name = error instanceof Error ? error.name : "";
  const code = error instanceof WebAuthnError ? error.code : "";
  if (name === "NotAllowedError" || name === "AbortError" || code === "ERROR_CEREMONY_ABORTED") return new PasskeyCancelled();
  if (code === "ERROR_AUTHENTICATOR_PREVIOUSLY_REGISTERED") return new Error(t`This device already has a passkey for your account.`);
  if (code === "ERROR_INVALID_DOMAIN" || code === "ERROR_INVALID_RP_ID" || name === "SecurityError") {
    return new Error(t`Passkeys can't be used on this address. Open Space Works from its usual address to use one.`);
  }
  return new Error(t`Your device couldn't use a passkey just now. Try again, or use another way to sign in.`);
}

export async function getPasskeyAssertion(options: unknown, autofill = false) {
  try {
    return await startAuthentication({ optionsJSON: options as PublicKeyCredentialRequestOptionsJSON, useBrowserAutofill: autofill });
  } catch (error) { throw translate(error); }
}

export async function createPasskey(options: unknown) {
  try {
    return await startRegistration({ optionsJSON: options as PublicKeyCredentialCreationOptionsJSON });
  } catch (error) { throw translate(error); }
}

export const isPasskeyCancelled = (error: unknown) => error instanceof PasskeyCancelled;
