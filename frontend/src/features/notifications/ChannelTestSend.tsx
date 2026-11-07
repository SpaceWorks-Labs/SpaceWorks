import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Field } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { DESTINATIONS_KEY } from "../staff/notificationDestinations/channels";
import type { NotificationDestination } from "../staff/notificationDestinationTypes";
import { useEndpoints, useTestChannel, type Channel } from "./channelsApi";

/**
 * Send a test through the saved settings: to one of this space's rooms, or to the Space
 * Manager's own connected account. The server answers with a sanitized result only.
 */
export function ChannelTestSend({ makerspaceId, channel }: { makerspaceId: number; channel: Channel }) {
  const rooms = useQuery({ queryKey: DESTINATIONS_KEY(makerspaceId), enabled: channel.room_enabled,
    queryFn: () => staffRequest<NotificationDestination[]>(`/admin/makerspace/${makerspaceId}/notification-destinations`) });
  const endpoints = useEndpoints(makerspaceId);
  const test = useTestChannel(makerspaceId);
  const options = [
    ...(channel.channel === "sms" && channel.personal_enabled ? [{ value: "sms:self", label: t`My verified phone (requires SMS consent)` }] : []),
    ...(channel.room_enabled ? (rooms.data ?? []).filter(room => room.channel === channel.channel && room.is_active)
      .map(room => ({ value: `room:${room.id}`, label: t`Room: ${room.label}` })) : []),
    ...(channel.personal_enabled ? (endpoints.data?.results ?? []).filter(row => row.channel === channel.channel
      && row.effective_valid && !row.revoked_at && row.integration_generation === channel.generation)
      .map(row => ({ value: `endpoint:${row.id}`, label: t`My connected account` })) : []),
  ];
  const [target, setTarget] = useState("");
  const chosen = options.some(option => option.value === target) ? target : options[0]?.value ?? "";
  if (!channel.enabled || channel.activation_hold) return null;
  if (!options.length) return <p className="text-sm text-muted">{t`To send a test, add a room for this channel or connect your own account under Inbox → My channels.`}</p>;
  const [kind, id] = chosen.split(":");
  return <div className="grid min-w-0 gap-2 rounded-lg border border-line p-3">
    <Field label={t`Send a test to`}><select className="desk-input" value={chosen} onChange={event => setTarget(event.target.value)}>
      {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></Field>
    <div><button type="button" className="desk-button" disabled={test.isPending}
      onClick={() => test.mutate({ channel: channel.channel, ...(kind === "sms" ? {} : kind === "room" ? { room_id: Number(id) } : { endpoint_id: Number(id) }) })}>
      {test.isPending ? t`Sending…` : t`Send test`}</button></div>
    {test.data ? <p role="status" className={`text-sm ${test.data.accepted ? "text-muted" : "text-danger"}`}>
      {test.data.accepted ? t`Test accepted by the provider.` : t`Test failed: ${test.data.sanitized_error || test.data.error_code || "unknown error"}.`}</p> : null}
    {test.error ? <p role="alert" className="text-sm text-danger">{test.error.message}</p> : null}
  </div>;
}
