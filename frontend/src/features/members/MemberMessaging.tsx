import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { StatusPill } from "../../components/ui";
import { memberRequest } from "../../lib/api";
import { MessagingError } from "../messaging/MessagingFeedback";
import { memberMessagingKey, messagingLabels, useMemberMessaging, type MessagingConsentWrite, type MemberMessaging as MemberMessagingData } from "../messaging/messagingApi";

export function MemberMessaging({ makerspaceId, verifyPhoneHref }: { makerspaceId: number; verifyPhoneHref: string }) {
  const client = useQueryClient();
  const settings = useMemberMessaging(makerspaceId);
  const consent = useMutation({ mutationFn: (body: MessagingConsentWrite) => memberRequest<MemberMessagingData>("/me/messaging/consent", {
    method: "POST", body: JSON.stringify(body),
  }), onSuccess: data => {
    client.setQueryData(memberMessagingKey(makerspaceId), data);
    return client.invalidateQueries({ queryKey: memberMessagingKey(makerspaceId), exact: true });
  } });
  return <section className="desk-panel grid gap-4 p-5">
    <h2 className="title-panel">SMS & WhatsApp notifications</h2>
    <p className="text-sm text-muted">Choose whether this makerspace may message your verified phone. Consent is separate for each channel and makerspace.</p>
    {settings.isPending ? <p role="status">Loading messaging preferences…</p> : null}
    <MessagingError error={settings.error} />
    {settings.isError ? <button type="button" className="desk-button w-fit" onClick={() => void settings.refetch()}>Retry messaging preferences</button> : null}
    {settings.data ? (["sms", "whatsapp"] as const).map(channel => {
      const state = settings.data[channel];
      return <section key={channel} className="grid gap-2 rounded-md border border-line p-3">
        <div className="flex flex-wrap items-center gap-3"><h3 className="title-section">{messagingLabels[channel]}</h3><StatusPill label={state.available ? "Available" : "Unavailable"} tone={state.available ? "success" : "neutral"} /></div>
        <p className="text-sm text-muted">Phone: {state.phone_masked || "No phone linked"}</p>
        {!state.available ? <p className="text-sm text-muted">This makerspace has no available {messagingLabels[channel]} sender. You can still withdraw consent.</p> : null}
        {!state.phone_verified ? <Link className="desk-button w-fit" to={verifyPhoneHref}>Verify your phone first</Link> : null}
        {state.suppressed ? <p className="text-sm text-warn-ink">You replied STOP; turning this on again re-subscribes you.</p> : null}
        <label className="flex min-h-11 items-center gap-2 text-sm font-semibold"><input className="h-4 w-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" type="checkbox"
          checked={state.consented} disabled={consent.isPending || (!state.consented && (!state.phone_verified || !state.available))}
          onChange={event => consent.mutate({ makerspace: makerspaceId, channel, action: event.target.checked ? "opted_in" : "opted_out" })} />Allow {messagingLabels[channel]} notifications</label>
      </section>;
    }) : null}
    <MessagingError error={consent.error} />
    {consent.isSuccess ? <p role="status" className="text-sm text-success-ink">Messaging consent saved.</p> : null}
  </section>;
}
