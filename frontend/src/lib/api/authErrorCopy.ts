/**
 * Plain-language copy for the sign-in and account-security error codes (release 2, lane S-D).
 *
 * The codes are the frozen names in `accounts/login_security_contract.py` (plus the existing
 * `recent_reauth_required`). A screen shows `authErrorMessage(error)` instead of the raw server
 * text, so no screen ever shows a code, and a breached password is never described as "hacked".
 */
import { formatLocale } from "../format";
import { t } from "@lingui/core/macro";
import { StructuredApiError } from "./errors";

const COPY: Record<string, string> = {
  captcha_required: t`Confirm you're a person to continue.`,
  captcha_failed: t`That check didn't go through. Try it again.`,
  password_breached: t`This password has appeared in a known data breach elsewhere, so it's easy to guess. Choose a different one.`,
  login_code_required: t`Enter the code we emailed you to finish signing in.`,
  login_code_invalid: t`That code didn't match or has expired. Check the latest email, or send a new code.`,
  native_app_update_required: t`Update the Space Works app to the latest version, then sign in again.`,
  passkey_failed: t`That passkey didn't work here. Try again, or use another way to sign in.`,
  passkeys_unavailable: t`Passkeys are turned off for your account. Use your authenticator app instead.`,
  passkey_required: t`Your account confirms with a passkey. Use your passkey to continue.`,
  rp_id_unavailable: t`Passkeys can't be used on this address. Open Space Works from its usual address to use one.`,
  last_factor: t`Staff need a second factor. Set up an authenticator or another passkey before removing this one.`,
  security_alert_used: t`This link was already used or has expired. If you still don't recognise the activity, reset your password.`,
  staff_network_refused: t`Staff screens of this space only open from its approved networks. Your member area still works.`,
  staff_session_expired: t`Your staff session has ended. Sign in again to keep using staff screens.`,
  mfa_enrollment_required: t`Set up two-step sign-in to keep using staff screens. Your member area still works.`,
  recent_reauth_required: t`Confirm it's you, then try again.`,
};

function formatWait(seconds: number) {
  if (seconds < 90) return "in about a minute";
  const minutes = Math.round(seconds / 60);
  if (minutes < 90) return `in about ${minutes} minutes`;
  const at = new Date(Date.now() + seconds * 1000);
  return `after ${at.toLocaleTimeString(formatLocale(), { hour: "numeric", minute: "2-digit" })}`;
}

/** The code of a structured API error, if it carries one. */
export function authErrorCode(error: unknown) {
  return error instanceof StructuredApiError ? error.code : undefined;
}

/** What to show for an auth error; `fallback` (or the server's text) for anything else. */
export function authErrorMessage(error: unknown, fallback = "Something went wrong. Try again.") {
  const code = authErrorCode(error);
  if (code === "ip_blocked") {
    const wait = error instanceof StructuredApiError ? error.retryAfterSeconds : undefined;
    return wait ? t`Too many failed sign-ins from your network. Try again ${formatWait(wait)}.` : t`Too many failed sign-ins from your network. Try again later.`;
  }
  if (code && COPY[code]) return COPY[code];
  if (error instanceof Error && error.message && !/^Request failed \(\d+\)$/.test(error.message)) return error.message;
  return fallback;
}

/** The Turnstile challenge a 400 `captcha_required`/`captcha_failed` asks for, if any. */
export function captchaChallenge(error: unknown) {
  if (!(error instanceof StructuredApiError) || (error.code !== "captcha_required" && error.code !== "captcha_failed")) return null;
  const siteKey = typeof error.body.turnstile_site_key === "string" ? error.body.turnstile_site_key : "";
  const action = typeof error.body.turnstile_action === "string" ? error.body.turnstile_action : "login";
  return { siteKey, action };
}
