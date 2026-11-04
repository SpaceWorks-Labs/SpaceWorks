import { useRef, useState } from "react";
import { eventErrorText } from "../eventUi";
import { useBroadcastCommand, type BroadcastCampaign, type BroadcastPreview } from "./broadcastApi";
import { isProtectedDenial } from "./sessionScope";
import { BroadcastTalliesRow } from "./BroadcastTalliesRow";
import { BroadcastUndoBar } from "./BroadcastUndoBar";

export function BroadcastDeliveryControls({ makerspaceId, eventId, campaign }: { makerspaceId: number; eventId: number; campaign: BroadcastCampaign }) {
  const [mode, setMode] = useState<"desktop" | "mobile">("desktop");
  const [confirmed, setConfirmed] = useState(false);
  const [sendAt, setSendAt] = useState(() => { const date = new Date(Date.now() + 120000); return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16); });
  const ids = useRef(new Map<string, string>());
  const preview = useBroadcastCommand<BroadcastPreview>(makerspaceId, eventId, campaign.id, "preview");
  const test = useBroadcastCommand<{ state: string }>(makerspaceId, eventId, campaign.id, "test");
  const schedule = useBroadcastCommand<BroadcastCampaign>(makerspaceId, eventId, campaign.id, "schedule");
  const cancel = useBroadcastCommand<BroadcastCampaign>(makerspaceId, eventId, campaign.id, "cancel");
  const send = useBroadcastCommand<BroadcastCampaign>(makerspaceId, eventId, campaign.id, "send");
  const latest = cancel.data ?? send.data ?? campaign;
  const holding = latest.undo_hold && latest.status === "scheduled" && !!latest.available_at;
  const command = (action: string, body = {}, version = campaign.version) => {
    const digest = JSON.stringify([campaign.id, version, action, body]);
    if (!ids.current.has(digest)) ids.current.set(digest, crypto.randomUUID());
    return { ...body, operation_id: ids.current.get(digest)!, expected_version: version };
  };
  const result = preview.data;
  const error = preview.error || test.error || schedule.error || send.error || cancel.error;
  if (isProtectedDenial(error)) return <p role="alert" className="text-sm text-danger">This broadcast is no longer available for your access.</p>;
  return <div className="grid gap-3">
    <div className="flex flex-wrap gap-2">{campaign.render_schema_version === 2 && campaign.status === "draft" ? <button className="desk-button" type="button" disabled={preview.isPending} onClick={() => { setConfirmed(false); preview.mutate(command("preview")); }}>Preview audience and message</button> : null}
      {["draft", "scheduled", "queued", "sending"].includes(latest.status) && !holding ? <button className="desk-button-danger-outline" type="button" disabled={cancel.isPending} onClick={() => cancel.mutate(campaign.render_schema_version === 2 ? command("cancel", {}, latest.version) : {})}>Cancel broadcast</button> : null}</div>
    {holding ? <BroadcastUndoBar until={latest.available_at!} busy={cancel.isPending} onUndo={() => cancel.mutate(command("cancel", {}, latest.version))} /> : null}
    {cancel.data?.status === "cancelled" ? <p role="status" className="text-sm">Broadcast cancelled. Nothing further will be sent.</p> : null}
    {campaign.render_schema_version !== 2 || campaign.status !== "draft" ? <div className="grid gap-2"><p className="whitespace-pre-wrap rounded-xl border border-line bg-surface p-3 text-sm">{campaign.body}</p><p className="text-xs text-muted">Reuse this message to create a new draft with a current audience preview.</p></div> : null}
    {result ? <div className="grid gap-3 rounded-xl border border-line bg-surface p-3">
      <p className="text-sm font-semibold">{result.recipient_count} eligible recipients at this revision</p>
      <div className="flex gap-2"><button type="button" className="desk-button" aria-pressed={mode === "desktop"} onClick={() => setMode("desktop")}>Desktop</button><button type="button" className="desk-button" aria-pressed={mode === "mobile"} onClick={() => setMode("mobile")}>Mobile</button></div>
      <iframe sandbox="allow-same-origin" title={`${mode === "desktop" ? "Desktop" : "Mobile"} message preview`} srcDoc={mode === "desktop" ? result.desktop_html : result.mobile_html} className={`h-96 w-full rounded-xl border border-line bg-white ${mode === "mobile" ? "max-w-[375px]" : ""}`} />
      <details><summary className="min-h-11 cursor-pointer text-sm">Plain-text preview</summary><p className="whitespace-pre-wrap text-sm">{result.text}</p></details>
      <button type="button" className="desk-button justify-self-start" disabled={test.isPending} onClick={() => test.mutate(command("test", { preview_id: result.preview_id }))}>Send test to myself</button>
      {test.isSuccess ? <p role="status" className="text-sm">{test.data.state === "queued" ? "Test queued for your own verified address." : test.data.state === "skipped" ? "Test was skipped by your delivery preferences or address eligibility." : "The test could not be queued. Check delivery settings."}</p> : null}
      {campaign.status === "draft" ? <><label className="grid gap-1 text-sm">Send at (your local time)<input type="datetime-local" className="desk-input" value={sendAt} onChange={e => setSendAt(e.target.value)} /></label>
        <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />I confirm this message and {result.recipient_count} recipients</label>
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" className="desk-button" disabled={!confirmed || !sendAt || new Date(sendAt).getTime() < Date.now() + 10000 || schedule.isPending || send.isPending} onClick={() => schedule.mutate(command("schedule", { preview_id: result.preview_id, revision: result.revision, recipient_count: result.recipient_count, confirm: true, available_at: new Date(sendAt).toISOString() }))}>Schedule broadcast</button>
          <button type="button" className="desk-button-primary" disabled={!confirmed || send.isPending || schedule.isPending || !!send.data} onClick={() => send.mutate(command("send", { preview_id: result.preview_id, revision: result.revision, recipient_count: result.recipient_count, confirm: true }))}>Send now</button>
        </div>
        <p className="text-xs text-muted">Send now waits five seconds so you can undo. A scheduled send must be at least five seconds away. The server rechecks the audience, sender access and quiet hours before delivery.</p></> : null}
    </div> : null}
    {error ? <p role="alert" className="text-sm text-danger">{eventErrorText(error)}</p> : null}
    {schedule.isSuccess ? <p role="status" className="text-sm">Broadcast scheduled.</p> : null}
    {campaign.render_schema_version === 2 ? <BroadcastTalliesRow makerspaceId={makerspaceId} eventId={eventId} campaignId={campaign.id} status={latest.status} /> : null}
  </div>;
}
