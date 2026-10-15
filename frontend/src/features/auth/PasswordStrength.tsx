import { ProgressBar } from "../../components/ui";

/** Guidance mirrors the existing eight-character floor; the server owns password policy. */
export function PasswordStrength({ password }: { password: string }) {
  const checks = [password.length >= 8, password.length >= 12, /[0-9]/.test(password) && /[^a-zA-Z0-9]/.test(password)];
  const labels = ["At least 8 characters", "12 or more characters is stronger", "Add a number and symbol for strength"];
  return <div className="grid gap-2 text-sm text-muted" aria-live="polite">
    <ProgressBar value={checks.filter(Boolean).length / checks.length} label="Password strength" />
    <ul className="grid gap-1">{labels.map((label, index) => <li key={label} className="flex items-start gap-2">
      <span aria-hidden="true">{checks[index] ? "✓" : "·"}</span><span>{label}</span>
    </li>)}</ul>
  </div>;
}
