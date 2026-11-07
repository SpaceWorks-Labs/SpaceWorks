import { t } from "@lingui/core/macro";
import { Fingerprint } from "lucide-react";

/** "Sign in with a passkey" beside the provider buttons; the browser's own sheet does the rest. */
export function PasskeySignInButton({ pending, error, onClick }: { pending: boolean; error: string; onClick: () => void }) {
  return <div className="grid gap-2">
    <button type="button" className="desk-button min-h-11 w-full gap-2" disabled={pending} aria-busy={pending || undefined} onClick={onClick}>
      <Fingerprint aria-hidden="true" size={20} />{pending ? t`Waiting for your passkey…` : t`Sign in with a passkey`}
    </button>
    <p role="alert" className="text-sm text-danger empty:hidden">{error}</p>
  </div>;
}
