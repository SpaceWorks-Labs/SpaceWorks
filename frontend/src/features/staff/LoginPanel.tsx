import { useState } from "react";
import { AuthLayout } from "../../components/layouts";
import { AuthShowcase } from "../auth/AuthShowcase";
import { PasswordInput } from "../auth/PasswordInput";

export function LoginPanel({ error, guestOnly, isPending, onSubmit, platform = false }: {
  error?: string;
  guestOnly: boolean;
  isPending: boolean;
  onSubmit: (payload: { username: string; password: string }) => void;
  platform?: boolean;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  return <AuthLayout state={{ status: "ready" }} eyebrow={platform ? "Platform console" : guestOnly ? "Front desk" : "Staff console"}
    title="Welcome back." brand={{ showcase: <AuthShowcase /> }}
    form={<form className="grid gap-4" onSubmit={(event) => {
      event.preventDefault();
      if (!isPending && username.trim() && password) onSubmit({ username: username.trim(), password });
    }}>
      <p className="text-sm text-muted">{platform ? "Sign in with your separate platform account. Staff sign in from their makerspace's page."
        : "Sign in with the staff account issued for this makerspace. Ask your Space Manager if you need a password."}</p>
      <label className="grid gap-2 text-sm font-semibold" htmlFor="staff-username">Username or email
        <input id="staff-username" className="desk-input w-full" name="username" autoComplete="username" required
          value={username} onChange={(event) => setUsername(event.target.value)} />
      </label>
      <label className="text-sm font-semibold" htmlFor="staff-password">Password</label>
      <PasswordInput id="staff-password" name="password" autoComplete="current-password"
        value={password} onChange={(event) => setPassword(event.target.value)} />
      {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
      <button className="desk-button-primary w-full" type="submit" disabled={isPending || !username.trim() || !password}>
        {isPending ? "Signing in?" : "Sign in"}
      </button>
    </form>} />;
}
