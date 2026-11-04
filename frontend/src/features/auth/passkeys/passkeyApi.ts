/** S-A's passkey routes (`/api/v1/auth/passkeys*`, `auth/mfa/passkey/options`, `auth/reauth/passkey*`). */
import type {
  PasskeyList, PasskeyLogin, PasskeyOptions, PasskeyReauthenticated, PasskeyRegistered, PasskeyRemoved, Passkey,
} from "../../../generated/api";
import { publicV1Request, staffRequest } from "../../../lib/api";
import { mfaRequest } from "../mfaApi";
import { createPasskey, getPasskeyAssertion } from "./webauthn";

const post = (body: unknown) => ({ method: "POST", body: JSON.stringify(body) });

export const listPasskeys = () => staffRequest<PasskeyList>("/auth/passkeys");
export const renamePasskey = (id: number, name: string) =>
  staffRequest<Passkey>(`/auth/passkeys/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
/** Ends every session; the calling browser gets a new one unless the passkey was its only proof. */
export const removePasskey = (id: number) => staffRequest<PasskeyRemoved>(`/auth/passkeys/${id}`, { method: "DELETE" });

/** Add a passkey. The options call needs recent re-authentication, which the shared client asks for. */
export async function registerPasskey(name: string) {
  const { ceremony, options } = await staffRequest<PasskeyOptions>("/auth/passkeys/register/options", post({}));
  const credential = await createPasskey(options);
  return staffRequest<PasskeyRegistered>("/auth/passkeys/register/verify", post({ ceremony, credential, name }));
}

/** Passwordless sign-in, step 1: a ceremony for any passkey on this address. */
export const passkeySignInOptions = () => publicV1Request<PasskeyOptions>("/auth/passkeys/authenticate/options",
  { ...post({}), credentials: "include" });

/** Step 2: the browser's sheet (or, with `autofill`, the email field's list), then the session. */
export async function finishPasskeySignIn({ ceremony, options }: PasskeyOptions, autofill = false) {
  const credential = await getPasskeyAssertion(options, autofill);
  return publicV1Request<PasskeyLogin>("/auth/passkeys/authenticate/verify",
    { ...post({ ceremony, credential }), credentials: "include" });
}

/** The second factor of a pending challenge: `mfa/verify` with `factor=passkey` and `webauthn`.
 *  STUB(S-B): matches S-B's `MFAVerifySerializer` on lane/r2-s-b (efae28ce); live once S-B merges. */
export async function verifyPasskeyFactor<T>(challenge: string) {
  const { ceremony, options } = await mfaRequest<PasskeyOptions>("/auth/mfa/passkey/options", { challenge });
  const credential = await getPasskeyAssertion(options);
  return mfaRequest<T>("/auth/mfa/verify", { challenge, factor: "passkey", webauthn: { ceremony, credential } });
}

/** Re-authentication for the ten-minute window. */
export async function reauthenticateWithPasskey() {
  const { ceremony, options } = await staffRequest<PasskeyOptions>("/auth/reauth/passkey/options", post({}));
  const credential = await getPasskeyAssertion(options);
  return staffRequest<PasskeyReauthenticated>("/auth/reauth/passkey", post({ ceremony, credential }));
}
