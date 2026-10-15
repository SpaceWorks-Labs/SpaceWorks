import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { publicV1Request } from "../../lib/api";
import { AuthLayout } from "../../components/layouts";
import { AuthShowcase } from "../auth/AuthShowcase";
import { PasswordInput } from "../auth/PasswordInput";
import { SocialSignInButtons } from "../auth/SocialSignInButtons";
import type { SocialLoginResult } from "../auth/socialSdk";
import { MfaFlow } from "../auth/MfaFlow";
import type { MfaChallenge } from "../auth/mfaApi";

export function LoginPanel({
  error,
  guestOnly,
  isPending,
  onSubmit,
  onSocialSuccess,
}: {
  error?: string;
  guestOnly: boolean;
  isPending: boolean;
  onSubmit: (payload: { username: string; password: string }) => void;
  onSocialSuccess?: (result: SocialLoginResult) => void;
}) {
  const [challenge, setChallenge] = useState<MfaChallenge>();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [emailEnabled, setEmailEnabled] = useState(false);
  // Present in the config only when password sign-in has been switched off, so an
  // absent key — and a failed request — mean it is available.
  const [passwordLogin, setPasswordLogin] = useState(true);
  useEffect(() => {
    let active = true;
    publicV1Request<{ email_enabled: boolean; password_login?: { enabled: boolean } }>(
      "/config",
    )
      .then((config) => {
        if (active) {
          setEmailEnabled(config.email_enabled === true);
          setPasswordLogin(config.password_login?.enabled !== false);
        }
      })
      .catch(() => {
        if (active) {
          setEmailEnabled(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);
  if (challenge && onSocialSuccess) return <MfaFlow challenge={challenge} onCancel={() => setChallenge(undefined)}
    onComplete={(result) => { setChallenge(undefined); onSocialSuccess({ access: result.access, user: result.user as unknown as Record<string, unknown>, outcome: "existing" }); }} />;
  return <AuthLayout state={{ status: "ready" }} eyebrow={guestOnly ? "Front desk" : "Staff console"}
    title="Welcome back." brand={{ showcase: <AuthShowcase /> }} dividerLabel="or with your username"
    social={onSocialSuccess ? <SocialSignInButtons surface="staff" onMfaChallenge={setChallenge} onSuccess={onSocialSuccess} /> : undefined}
    form={<form className="grid gap-4" onSubmit={(event) => {
      event.preventDefault();
      if (!isPending) onSubmit({ username, password });
    }}>
      <p className="text-sm text-muted">{passwordLogin
        ? "Use your staff account to manage requests, inventory, and handovers."
        : "This deployment signs staff in through an identity provider."}</p>
      {passwordLogin ? <>
        <label className="grid gap-2 text-sm font-semibold" htmlFor="staff-username">Username
          <input id="staff-username" className="desk-input w-full" name="username" autoComplete="username"
            value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <div className="flex items-center justify-between gap-3">
          <label className="text-sm font-semibold" htmlFor="staff-password">Password</label>
          {emailEnabled ? <Link className="desk-button-ghost text-sm" to="/reset-password">Forgot password?</Link> : null}
        </div>
        <PasswordInput id="staff-password" name="password" autoComplete="current-password"
          value={password} onChange={(event) => setPassword(event.target.value)} />
      </> : null}
      {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
      {passwordLogin ? <button className="desk-button-primary w-full" type="submit" disabled={isPending}>
        {isPending ? "Signing in…" : "Sign in"}
      </button> : null}
    </form>} />;
}
