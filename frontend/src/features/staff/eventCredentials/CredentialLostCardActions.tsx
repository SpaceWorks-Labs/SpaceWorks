import { t } from "@lingui/core/macro";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ActionControl } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { eventErrorText } from "../eventUi";

type Result = { id: number; event_id: number; version: number; state: "applied"; credential_generation?: number | null };

/**
 * Lost or compromised event QR credential (check-in staff): "Replace QR" issues a new
 * generation and voids the old one; "Disable QR" voids it without a replacement. Both
 * advance the event version, so the roster reloads the event afterwards.
 */
export function CredentialLostCardActions({ eventId, registrationId, version }: {
  eventId: number; registrationId: number; version?: number;
}) {
  const client = useQueryClient();
  const command = useMutation({
    mutationFn: (action: "rotate" | "revoke") => staffRequest<Result>(
      `/admin/events/${eventId}/registrations/${registrationId}/credential/${action}/`,
      { method: "POST", body: JSON.stringify({ operation_id: crypto.randomUUID(), expected_version: version }) }),
    onSettled: () => { void client.invalidateQueries({ queryKey: ["event", eventId] }); },
  });
  const noVersion = version === undefined;
  const reason = noVersion ? t`Reload the event first.` : undefined;
  return <>
    <ActionControl action={{ label: t`Replace QR`, pending: command.isPending && command.variables === "rotate", disabled: noVersion, disabledReason: reason,
      confirm: { title: t`Replace this guest's QR?`, message: t`Their old ticket and badge QR stop working. Reprint the ticket or badge after replacing it.` },
      onClick: () => command.mutate("rotate") }} />
    <ActionControl action={{ label: t`Disable QR`, tone: "danger", pending: command.isPending && command.variables === "revoke", disabled: noVersion, disabledReason: reason,
      confirm: { title: t`Disable this guest's QR?`, message: t`Their ticket and badge QR stop working until a new one is issued at the desk.` },
      onClick: () => command.mutate("revoke") }} />
    {command.isSuccess ? <span role="status" className="text-xs text-muted">{command.variables === "rotate" ? t`New QR issued.` : t`QR disabled.`}</span> : null}
    {command.error ? <p role="alert" className="text-xs text-danger">{eventErrorText(command.error)}</p> : null}
  </>;
}
