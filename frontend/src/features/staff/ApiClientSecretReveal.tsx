import { t } from "@lingui/core/macro";
import { Callout } from "../../components/ui";

/** A show-once client secret, with copy and dismiss. Used after create and after rotate. */
export function ApiClientSecretReveal({ secret, onDismiss }: { secret: string; onDismiss: () => void }) {
  return (
    <div className="mt-3 rounded-md border border-line bg-warn-soft p-3">
      <Callout size="inline" tone="warn" lead="Copy the secret now." body="It’s shown once." />
      <p className="mt-2 break-all rounded-md border border-line bg-bg p-2 code-text text-xs text-ink">{secret}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="desk-button" type="button" onClick={() => void navigator.clipboard.writeText(secret)}>{t`Copy`}</button>
        <button className="desk-button-primary" type="button" onClick={onDismiss}>{t`Done`}</button>
      </div>
    </div>
  );
}
