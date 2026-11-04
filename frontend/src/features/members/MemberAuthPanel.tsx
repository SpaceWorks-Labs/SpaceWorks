import { MfaFlow } from "../auth/MfaFlow";
import { isMfaChallenge, type MfaChallenge } from "../auth/mfaApi";
import { useEffect, useState, type ReactNode } from "react";
import { AuthLayout } from "../../components/layouts";
import { SegmentedControl } from "../../components/ui";
import { AuthStepCard } from "../auth/AuthStepCard";
import { AuthShowcase } from "../auth/AuthShowcase";
import { PasswordInput } from "../auth/PasswordInput";
import { PasswordStrength } from "../auth/PasswordStrength";
import {
  publicV1Request,
  setAccessToken,
  staffRequest,
  type PasswordLoginRequest,
  type PasswordLoginResponse,
} from "../../lib/api";
import { SocialSignInButtons } from "../auth/SocialSignInButtons";
import { usePublicSignInConfig } from "../auth/usePublicSignInConfig";
import { PasskeySignInButton } from "../auth/passkeys/PasskeySignInButton";
import { usePasskeySignIn } from "../auth/passkeys/usePasskeySignIn";
import { tokenHeaders, useTurnstileGate } from "../../components/auth/useTurnstileGate";
import { authErrorCode, authErrorMessage } from "../../lib/api/authErrorCopy";

export function MemberAuthPanel({
  onAuthenticated,
  makerspaceSlug = "",
  tenantBrand,
  embedded = false,
  eyebrow,
  context,
  footer,
}: {
  onAuthenticated: () => void;
  makerspaceSlug?: string;
  tenantBrand?: { name: string; logo?: string };
  /** true inside another page (an action card, a ticket panel): no logo, no brand panel, no h1. */
  embedded?: boolean;
  /** Page variant only: a line naming why sign-in is being asked for (e.g. an invitation). */
  eyebrow?: string;
  /** Shown above the form, e.g. the reason for signing in or an error from the host page. */
  context?: ReactNode;
  /** Shown after the form, e.g. a way to back out of the host flow. */
  footer?: ReactNode;
}) {
  const [mfaChallenge, setMfaChallenge] = useState<MfaChallenge>();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [errorCode, setErrorCode] = useState<string>();
  const [notice, setNotice] = useState("");
  const [verificationOnly, setVerificationOnly] = useState(false);
  const [verificationCode, setVerificationCode] = useState("");
  const { selfServeAccounts, passwordLogin, passkeysEnabled, turnstileSiteKey } = usePublicSignInConfig();
  const signedIn = (result: PasswordLoginResponse) => {
    setAccessToken(result.access, "person");
    if (result.surface === "verification_only") {
      setVerificationOnly(true);
      setNotice("Enter the verification code sent to your email.");
    } else {
      onAuthenticated();
    }
  };
  const passkey = usePasskeySignIn({ enabled: passkeysEnabled && mode === "login" && !mfaChallenge && !verificationOnly, onSignedIn: signedIn });
  // A sign-in or sign-up the server answered with captcha_required: show the check, resend with its token.
  const captcha = useTurnstileGate(turnstileSiteKey, (token) => { void submit(token); });
  useEffect(() => {
    if (!selfServeAccounts) setMode("login");
  }, [selfServeAccounts]);
  const submit = async (captchaToken?: string) => {
    setPending(true);
    setError("");
    setErrorCode(undefined);
    setNotice("");
    try {
      if (mode === "signup") {
        await publicV1Request("/auth/member-sign-up", {
          method: "POST",
          headers: tokenHeaders(captchaToken),
          body: JSON.stringify({ display_name: displayName, email, phone, password, website: "" }),
        });
        captcha.reset();
        setMode("login");
        setNotice("Check your email to verify the new account, then sign in.");
      } else {
        const request = { username: email, password } satisfies PasswordLoginRequest;
        const result = await publicV1Request<PasswordLoginResponse | MfaChallenge>("/auth/login", {
          method: "POST",
          credentials: "include",
          headers: tokenHeaders(captchaToken),
          body: JSON.stringify(request),
        });
        captcha.reset();
        if (isMfaChallenge(result)) { setPassword(""); setMfaChallenge(result); return; }
        signedIn(result);
      }
    } catch (nextError) {
      if (!captcha.catchError(nextError)) {
        setError(authErrorMessage(nextError, "Unable to continue."));
        setErrorCode(authErrorCode(nextError));
      }
    } finally {
      setPending(false);
    }
  };
  const confirmVerification = async () => {
    setPending(true);
    setError("");
    try {
      await staffRequest("/auth/email-verification/confirm", {
        method: "POST",
        body: JSON.stringify({ code: verificationCode }),
      });
      onAuthenticated();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to verify email.");
    } finally {
      setPending(false);
    }
  };
  const resendVerification = async () => {
    setPending(true);
    setError("");
    try {
      await staffRequest("/auth/email-verification/resend", { method: "POST" });
      setNotice("If the details are valid, a verification email has been sent.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to resend the code.");
    } finally {
      setPending(false);
    }
  };
  if (mfaChallenge) return <MfaFlow embedded={embedded} eyebrow={eyebrow} extra={footer} challenge={mfaChallenge} turnstileSiteKey={turnstileSiteKey} onCancel={() => setMfaChallenge(undefined)}
    onComplete={(result) => { setAccessToken(result.access, "person"); setMfaChallenge(undefined); if (result.surface === "verification_only") setVerificationOnly(true); else onAuthenticated(); }} />;
  if (verificationOnly) return <AuthStepCard embedded={embedded} eyebrow={eyebrow} footer={footer} state={{ status: "ready" }}
    media={{ icon: "Info", tone: "accent" }} title="Verify your email"
    body={<p>Enter the verification code sent to your email. This session can only verify the address until email ownership is confirmed.</p>}
    primary={{ label: "Verify email", pending, pendingLabel: "Please wait…", onClick: () => (document.getElementById("member-verify") as HTMLFormElement)?.requestSubmit() }}
    escape={{ label: "Resend code", disabled: pending, disabledReason: "Wait for verification to finish.", onClick: () => void resendVerification() }}
    content={<form id="member-verify" className="grid gap-3" onSubmit={(event) => { event.preventDefault(); if (!pending) void confirmVerification(); }}>
      <label className="grid gap-2 text-sm font-semibold" htmlFor="member-verification-code">Verification code
        <input id="member-verification-code" className="desk-input w-full" inputMode="numeric" autoComplete="one-time-code"
          value={verificationCode} onChange={(event) => setVerificationCode(event.target.value)} required />
      </label>
      {notice ? <p role="status" className="text-sm text-success-ink">{notice}</p> : null}
      {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
    <button type="submit" disabled={pending} hidden aria-hidden="true" tabIndex={-1} />
    </form>} />;
  const title = mode === "login" ? "Member sign in" : "Create a member account";
  const modeSwitch = selfServeAccounts ? { label: "Account access", value: mode,
    options: [{ value: "login", label: "Sign in" }, { value: "signup", label: "Create account" }],
    onChange: (next: string) => { setMode(next as "login" | "signup"); setError(""); captcha.reset(); } } : undefined;
  const passkeyButton = passkey.supported ? <PasskeySignInButton pending={passkey.pending} error={passkey.error} onClick={passkey.signIn} /> : null;
  const social = <>{passkeyButton}<SocialSignInButtons surface="member" onMfaChallenge={setMfaChallenge} email={email} makerspaceSlug={makerspaceSlug} onSuccess={(result) => {
    if (isMfaChallenge(result)) { setPassword(""); setMfaChallenge(result); return; }
    setAccessToken(result.access, "person"); onAuthenticated();
  }} /></>;
  const legal = selfServeAccounts ? "One account works at every makerspace you join." : "This space does not run self sign-up. Ask a staff member to add you.";
  const form = <form className="grid gap-4" onSubmit={(event) => { event.preventDefault(); if (!pending) void submit(); }}>
      <p className="text-sm text-muted">{mode === "signup" ? "Use one global account across every makerspace you join."
        : passwordLogin ? "Sign in to manage memberships, waivers, visits, and payments."
        : "This space signs members in through an identity provider."}</p>
      {mode === "signup" ? <label className="grid gap-2 text-sm font-semibold" htmlFor="member-name">Name
        <input id="member-name" className="desk-input w-full" autoComplete="name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} required />
      </label> : null}
      <label className="grid gap-2 text-sm font-semibold" htmlFor="member-email">Email
        <input id="member-email" className="desk-input w-full" type="email" autoComplete={mode === "login" && passkey.autofill ? "username webauthn" : "email"} value={email} onChange={(event) => setEmail(event.target.value)} required />
      </label>
      {passwordLogin || mode === "signup" ? <>
        <label className="text-sm font-semibold" htmlFor="member-password">Password</label>
        <PasswordInput id="member-password" autoComplete={mode === "login" ? "current-password" : "new-password"}
          value={password} onChange={(event) => setPassword(event.target.value)} required />
        {mode === "signup" ? <PasswordStrength password={password} /> : null}
      </> : null}
      {mode === "signup" ? <label className="grid gap-2 text-sm font-semibold" htmlFor="member-phone">Phone (optional)
        <input id="member-phone" className="desk-input w-full" autoComplete="tel" value={phone} onChange={(event) => setPhone(event.target.value)} />
      </label> : null}
      {notice ? <p role="status" className="text-sm text-success-ink">{notice}</p> : null}
      {captcha.slot}
      {error ? <p className="text-sm text-danger" role="alert">{error}{errorCode === "password_breached" ? <> <a className="font-semibold underline" href="#member-password"
        onClick={(event) => { event.preventDefault(); document.getElementById("member-password")?.focus(); }}>Choose another password</a></> : null}</p> : null}
      {passwordLogin || mode === "signup" ? <button className="desk-button-brand w-full" type="submit" disabled={pending}>
        {pending ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
      </button> : null}
    <button type="submit" disabled={pending} hidden aria-hidden="true" tabIndex={-1} />
    </form>;
  // Embedded in another page's card: the same controls under that page's own heading.
  if (embedded) return <section aria-label={title} className="grid min-w-0 gap-4">
    {context}
    {modeSwitch ? <SegmentedControl {...modeSwitch} fullWidth /> : null}
    <div className="grid gap-3 empty:hidden">{social}</div>
    <p className="flex items-center gap-3 text-center text-sm text-muted [:empty+&]:hidden">
      <span className="h-px flex-1 bg-line" />or with email<span className="h-px flex-1 bg-line" /></p>
    {form}
    <p className="text-sm text-muted">{legal}</p>
    {footer}
  </section>;
  return <AuthLayout state={{ status: "ready" }} eyebrow={eyebrow} title={title}
    brand={{ tenant: tenantBrand, showcase: <AuthShowcase /> }}
    modeSwitch={modeSwitch} social={social}
    legal={footer ? <div className="grid gap-4"><p>{legal}</p>{footer}</div> : legal}
    form={context ? <div className="grid gap-4">{context}{form}</div> : form} />;
}
