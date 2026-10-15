import { MfaFlow } from "../auth/MfaFlow";
import { isMfaChallenge, type MfaChallenge } from "../auth/mfaApi";
import { useEffect, useState } from "react";
import { AuthLayout, CenteredCardLayout } from "../../components/layouts";
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

export function MemberAuthPanel({
  onAuthenticated,
  makerspaceSlug = "",
  tenantBrand,
}: {
  onAuthenticated: () => void;
  makerspaceSlug?: string;
  tenantBrand?: { name: string; logo?: string };
}) {
  const [mfaChallenge, setMfaChallenge] = useState<MfaChallenge>();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [verificationOnly, setVerificationOnly] = useState(false);
  const [verificationCode, setVerificationCode] = useState("");
  // Each of these appears in the public config only when it has been switched off, so
  // an absent key — and a failed request — mean available.
  const [selfServeAccounts, setSelfServeAccounts] = useState(true);
  const [passwordLogin, setPasswordLogin] = useState(true);
  useEffect(() => {
    publicV1Request<{
      member_accounts?: { enabled: boolean };
      self_registration?: { enabled: boolean };
      password_login?: { enabled: boolean };
    }>("/config")
      .then((result) => {
        setSelfServeAccounts(
          result.member_accounts?.enabled !== false &&
            result.self_registration?.enabled !== false,
        );
        setPasswordLogin(result.password_login?.enabled !== false);
      })
      .catch(() => {
        setSelfServeAccounts(true);
        setPasswordLogin(true);
      });
  }, []);
  useEffect(() => {
    if (!selfServeAccounts) setMode("login");
  }, [selfServeAccounts]);
  const submit = async () => {
    setPending(true);
    setError("");
    setNotice("");
    try {
      if (mode === "signup") {
        await publicV1Request("/auth/member-sign-up", {
          method: "POST",
          body: JSON.stringify({ display_name: displayName, email, phone, password, website: "" }),
        });
        setMode("login");
        setNotice("Check your email to verify the new account, then sign in.");
      } else {
        const request = {
          username: email,
          password,
          surface: "member",
        } satisfies PasswordLoginRequest;
        const result = await publicV1Request<PasswordLoginResponse | MfaChallenge>("/auth/login", {
          method: "POST",
          credentials: "include",
          body: JSON.stringify(request),
        });
        if (isMfaChallenge(result)) { setPassword(""); setMfaChallenge(result); return; }
        setAccessToken(result.access);
        if (result.surface === "verification_only") {
          setVerificationOnly(true);
          setNotice("Enter the verification code sent to your email.");
        } else {
          onAuthenticated();
        }
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to continue.");
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
  if (mfaChallenge) return <MfaFlow challenge={mfaChallenge} onCancel={() => setMfaChallenge(undefined)}
    onComplete={(result) => { setAccessToken(result.access); setMfaChallenge(undefined); if (result.surface === "verification_only") setVerificationOnly(true); else onAuthenticated(); }} />;
  if (verificationOnly) return <CenteredCardLayout state={{ status: "ready" }}
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
  return <AuthLayout state={{ status: "ready" }}
    title={mode === "login" ? "Member sign in" : "Create a member account"}
    brand={{ tenant: tenantBrand, showcase: <AuthShowcase /> }}
    modeSwitch={selfServeAccounts ? { label: "Account access", value: mode,
      options: [{ value: "login", label: "Sign in" }, { value: "signup", label: "Create account" }],
      onChange: (next) => { setMode(next as "login" | "signup"); setError(""); } } : undefined}
    social={<SocialSignInButtons surface="member" onMfaChallenge={setMfaChallenge} email={email} makerspaceSlug={makerspaceSlug} onSuccess={(result) => {
      if (isMfaChallenge(result)) { setPassword(""); setMfaChallenge(result); return; }
      setAccessToken(result.access); onAuthenticated();
    }} />}
    legal={selfServeAccounts ? "One account works at every makerspace you join." : "This space does not run self sign-up. Ask a staff member to add you."}
    form={<form className="grid gap-4" onSubmit={(event) => { event.preventDefault(); if (!pending) void submit(); }}>
      <p className="text-sm text-muted">{mode === "signup" ? "Use one global account across every makerspace you join."
        : passwordLogin ? "Sign in to manage memberships, waivers, visits, and payments."
        : "This space signs members in through an identity provider."}</p>
      {mode === "signup" ? <label className="grid gap-2 text-sm font-semibold" htmlFor="member-name">Name
        <input id="member-name" className="desk-input w-full" autoComplete="name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} required />
      </label> : null}
      <label className="grid gap-2 text-sm font-semibold" htmlFor="member-email">Email
        <input id="member-email" className="desk-input w-full" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
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
      {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
      {passwordLogin || mode === "signup" ? <button className="desk-button-brand w-full" type="submit" disabled={pending}>
        {pending ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
      </button> : null}
    <button type="submit" disabled={pending} hidden aria-hidden="true" tabIndex={-1} />
    </form>} />;
}
