import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Link } from "react-router-dom";
import { AuthLayout } from "../../components/layouts";
import { AuthShowcase } from "../auth/AuthShowcase";
import { PasswordInput } from "../auth/PasswordInput";

/**
 * The platform superadmin's own sign-in (`?context=platform`). It is the only separate
 * sign-in left: everyone else, staff included, signs in once with their own account.
 */
export function PlatformSignInPanel({ error, isPending, onSubmit }: {
  error?: string; isPending: boolean; onSubmit: (payload: { username: string; password: string }) => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  return <AuthLayout state={{ status: "ready" }} eyebrow={t`Platform console`} title={t`Welcome back.`}
    brand={{ showcase: <AuthShowcase /> }}
    form={<form className="grid gap-4" onSubmit={(event) => {
      event.preventDefault();
      if (!isPending && username.trim() && password) onSubmit({ username: username.trim(), password });
    }}>
      <p className="text-sm text-muted">{t`Sign in with the separate platform administrator account. Staff sign in with their own account from their makerspace.`}</p>
      <label className="grid gap-2 text-sm font-semibold" htmlFor="platform-username">{t`Username or email`}<input id="platform-username" className="desk-input w-full" name="username" autoComplete="username" required
          value={username} onChange={(event) => setUsername(event.target.value)} />
      </label>
      <label className="text-sm font-semibold" htmlFor="platform-password">{t`Password`}</label>
      <PasswordInput id="platform-password" name="password" autoComplete="current-password"
        value={password} onChange={(event) => setPassword(event.target.value)} />
      <Link className="justify-self-end text-sm font-semibold underline" to="/admin/reset-password?context=platform&step=request">{t`Forgot password?`}</Link>
      {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
      <button className="desk-button-primary w-full" type="submit" disabled={isPending || !username.trim() || !password}>
        {isPending ? t`Signing in…` : t`Sign in`}
      </button>
    </form>} />;
}
