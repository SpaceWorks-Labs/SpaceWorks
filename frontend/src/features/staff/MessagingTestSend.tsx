import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import { MessagingError } from "../messaging/MessagingFeedback";
import { messagingLabels, messagingSettingsPath, templateBindingsPath, type MessagingCatalogEntry,
  type MessagingTestResult, type MessagingTestWrite } from "../messaging/messagingApi";

export function MessagingTestSend({ makerspaceId, modules }: { makerspaceId: number; modules: string[] }) {
  const [eventKey, setEventKey] = useState("");
  const catalog = useQuery({ queryKey: ["whatsapp-template-catalog", makerspaceId],
    queryFn: () => staffRequest<MessagingCatalogEntry[]>(`${templateBindingsPath(makerspaceId)}/catalog`) });
  const entries = catalog.data?.filter(entry => entry.audience === "staff") ?? [];
  const selected = entries.find(entry => `${entry.feature}:${entry.event}` === eventKey) ?? entries[0];
  const send = useMutation({ mutationFn: (body: MessagingTestWrite) => staffRequest<MessagingTestResult>(`${messagingSettingsPath(makerspaceId)}/test`, {
    method: "POST", body: JSON.stringify(body),
  }) });
  return <section className="grid gap-3">
    <h3 className="title-section">Send a test</h3>
    <p className="text-sm text-muted">Tests go only to your own verified, consented number. Enable the selected event in the notification matrix first. Tests count toward quota and are limited to five per hour.</p>
    {catalog.isPending ? <p role="status">Loading test events…</p> : null}
    <MessagingError error={catalog.error} />
    {catalog.isError ? <button type="button" className="desk-button" onClick={() => void catalog.refetch()}>Retry test events</button> : null}
    {catalog.isSuccess && !entries.length ? <p>No reviewed staff events available for testing.</p> : null}
    {entries.length ? <label className="grid gap-1 text-sm">Test event<select className="desk-input" value={selected ? `${selected.feature}:${selected.event}` : ""} onChange={event => setEventKey(event.target.value)}>
      {entries.map(entry => <option key={`${entry.feature}:${entry.event}`} value={`${entry.feature}:${entry.event}`}>{entry.feature} / {entry.event}</option>)}
    </select></label> : null}
    <div className="flex flex-wrap gap-2">{(["sms", "whatsapp"] as const).filter(channel => modules.includes(channel)).map(channel => <button key={channel} type="button" className="desk-button" disabled={send.isPending || !selected}
      onClick={() => { if (selected) send.mutate({ channel, feature: selected.feature, event: selected.event }); }}>Send {messagingLabels[channel]} test</button>)}</div>
    <MessagingError error={send.error} />
    {send.data ? <p role="status" className="text-sm">{send.data.status === "pending" ? "Test queued; delivery is not yet confirmed." : `Test ${send.data.status}${send.data.skip_reason ? `: ${send.data.skip_reason}` : ""}.`}</p> : null}
  </section>;
}
