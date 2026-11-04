import { Fingerprint, Smartphone } from "lucide-react";
import { ActionControl, StatusPill } from "../../components/ui";
import { PasswordlessMfaProof } from "./PasswordlessMfaProof";

export type MfaStatus = { available: boolean; enabled: boolean; required: boolean; password_available?: boolean };

/**
 * The authenticator app part of the account security page: its state, the current-password
 * confirmation every change needs, and enrol / regenerate. A person who must enrol (staff
 * without a factor) is offered a passkey beside the authenticator (#128 C-1).
 */
export function MfaAuthenticatorSection({ status, hasPasskey, passkeysOffered, password, setPassword, busy, onEnroll, onRegenerate }: {
  status: MfaStatus; hasPasskey: boolean; passkeysOffered: boolean; password: string; setPassword: (value: string) => void;
  busy: boolean; onEnroll: () => void; onRegenerate: () => void;
}) {
  const { enabled, required } = status;
  // The deployment-level MFA switch: while it is off nobody can enroll or regenerate codes, but an
  // already-enrolled account keeps its authenticator and may still disable it.
  const available = status.available !== false;
  const manageable = available || enabled;
  // A passwordless account (social / OIDC sign-in only) cannot type a current password, so
  // enrollment is proven through PasswordlessMfaProof instead; managing an EXISTING
  // authenticator still needs a password the account does not have.
  const passwordAvailable = status.password_available !== false;
  const needsPassword = passwordAvailable || enabled;
  const mustEnrol = required && !enabled && !hasPasskey;
  return <div className="grid gap-4">
    <div className="flex flex-wrap items-center gap-3">
      <Smartphone aria-hidden="true" size={20} className="text-muted" />
      <StatusPill label={enabled ? "Authenticator on" : "Authenticator off"} tone={enabled ? "success" : "neutral"} />
      {hasPasskey ? <StatusPill label="Passkey saved" tone="success" /> : null}
    </div>
    <p className="text-sm text-muted">{!available ? "Two-step sign-in is turned off on this deployment."
      : enabled ? "Your authenticator is enrolled." : "Add an authenticator to protect your account."}
      {required ? " MFA is required for this account." : ""}</p>
    {mustEnrol ? <p className="rounded-xl border border-line bg-surface p-4 text-sm text-ink">
      Staff need an authenticator app or a passkey before the staff console opens. Your member area keeps working meanwhile.</p> : null}
    {!manageable ? null : passwordAvailable ? <label className="grid gap-2 text-sm font-semibold" htmlFor="mfa-password">Confirm your current password
      <input id="mfa-password" className="desk-input" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} /></label>
      : !enabled ? <PasswordlessMfaProof />
      : <p className="text-sm text-muted">Your existing MFA-management operations require a current password. Contact your administrator if you cannot supply one.</p>}
    {available ? <div className="flex flex-wrap gap-3">
      <ActionControl primary action={{
        label: enabled ? "Regenerate recovery codes" : "Enroll authenticator", pending: busy, disabled: needsPassword && !password,
        disabledReason: passwordAvailable ? "Confirm your current password to continue." : "Managing an enrolled authenticator requires a current password.",
        onClick: () => enabled ? onRegenerate() : onEnroll() }} />
      {!enabled && passkeysOffered ? <a href="#passkeys" className="desk-button min-h-11 gap-2"><Fingerprint aria-hidden="true" size={20} />Add a passkey instead</a> : null}
    </div> : null}
  </div>;
}
