import type { MfaChallenge, MfaFactor } from "./mfaApi";

/**
 * What a challenge may be answered with, in the server's order. A challenge from before S-B
 * carries no `factors[]`: then it is the authenticator, with a recovery code as the fallback.
 */
export function availableFactors(challenge: MfaChallenge): MfaFactor[] {
  if (challenge.enrollment_required) return ["totp"];
  const known: MfaFactor[] = ["totp", "passkey", "recovery", "email_code"];
  const listed = (challenge.factors ?? ["totp", "recovery"]).filter(factor => known.includes(factor));
  return listed.length ? listed : ["totp", "recovery"];
}

/** A passkey can only be offered where the browser can run the ceremony. */
export function usableFactors(challenge: MfaChallenge, passkeysSupported: boolean) {
  const factors = availableFactors(challenge).filter(factor => factor !== "passkey" || passkeysSupported);
  return factors.length ? factors : availableFactors(challenge);
}

export const SWITCH_LABEL: Record<MfaFactor, string> = {
  totp: "Use an authenticator code instead",
  passkey: "Use a passkey instead",
  recovery: "Use a recovery code instead",
  email_code: "Email me a code instead",
};

const RISK = "We don't recognise this device or network, so we need one more check.";

/** Title, body and field label for one factor. `legacy` keeps the pre-S-B wording. */
export function stepCopy(challenge: MfaChallenge, factor: MfaFactor) {
  const risk = challenge.purpose === "risk" ? `${RISK} ` : "";
  if (challenge.enrollment_required) {
    return { title: "Set up two-step sign-in", label: "Authenticator code",
      body: "Add Space Works to your authenticator app to secure this account. Staff need two-step sign-in before the staff console opens. Once you're signed in you can also add a passkey from Account security." };
  }
  if (factor === "passkey") {
    return { title: "Use your passkey", label: "",
      body: `${risk}Confirm with the passkey on this device, or a phone or security key that holds it.` };
  }
  if (factor === "recovery") {
    return { title: "Use a recovery code", label: "Recovery code", body: `${risk}Enter one of the recovery codes you saved. Each code works once.` };
  }
  if (factor === "email_code") {
    return { title: "Check your email", label: "Emailed code",
      body: `${risk}We emailed you a 6-digit code. It works once and expires after 10 minutes.` };
  }
  const legacy = !challenge.factors;
  return { title: "Enter your 6-digit code", label: legacy ? "Authenticator or recovery code" : "Authenticator code",
    body: legacy ? "Enter the code from your authenticator app, or one of your recovery codes."
      : `${risk}Enter the code from your authenticator app.` };
}
