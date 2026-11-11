import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Field } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import type { NotificationDestination } from "../notificationDestinationTypes";
import { DESTINATIONS_KEY } from "./channels";
import { SigningSecretReveal } from "./SigningSecretReveal";

type RotateResult = { destination: NotificationDestination; signing_secret: string; previous_valid_until: string | null };

/**
 * Replace a signed webhook's secret (parity A10). The old secret keeps verifying for the grace period
 * (0–168 hours; 0 retires it at once) so the receiving endpoint can switch without dropping alerts.
 */
export function RotateSigningSecret({ basePath, destination, makerspaceId, onClose }: {
  basePath: string; destination: NotificationDestination; makerspaceId: number; onClose: () => void;
}) {
  const client = useQueryClient();
  const [grace, setGrace] = useState("24");
  const hours = Number(grace);
  const valid = grace.trim() !== "" && Number.isInteger(hours) && hours >= 0 && hours <= 168;
  const rotate = useMutation({
    mutationFn: () => staffRequest<RotateResult>(`${basePath}/${destination.id}/rotate-secret`,
      { method: "POST", body: JSON.stringify({ grace_hours: hours }) }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: DESTINATIONS_KEY(makerspaceId) }); },
  });
  if (rotate.data) return <SigningSecretReveal secret={rotate.data.signing_secret} previousValidUntil={rotate.data.previous_valid_until} onDone={onClose} />;
  return <form className="grid gap-3 rounded-control border border-line bg-bg p-3" aria-label={t`Rotate signing secret for ${destination.label}`}
    onSubmit={event => { event.preventDefault(); if (valid) rotate.mutate(); }}>
    <p className="text-sm text-ink">{t`A new secret is made and shown once. Update your endpoint with it before the old one stops working.`}</p>
    <Field label={t`Keep the old secret working for (hours)`} hint={t`0 to 168. 0 stops the old secret now.`}
      error={valid ? undefined : t`Enter a whole number of hours from 0 to 168.`}>
      <input className="desk-input max-w-40" inputMode="numeric" value={grace} onChange={event => { setGrace(event.target.value); rotate.reset(); }} />
    </Field>
    {rotate.error ? <p role="alert" className="text-sm text-danger">{rotate.error.message}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button type="submit" className="desk-button-primary" disabled={!valid || rotate.isPending}>{rotate.isPending ? t`Rotating…` : t`Rotate secret`}</button>
      <button type="button" className="desk-button-ghost" onClick={onClose} disabled={rotate.isPending}>{t`Cancel`}</button>
    </div>
  </form>;
}
