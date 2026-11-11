import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ErrorText, Field, KeyValueCard, RelativeTime, StatusPill } from "../../components/ui";
import type { Tone } from "../../components/ui/types";
import { getSelfHostMove, requestSelfHostMove, type SelfHostMoveRequest } from "./selfHostMoveApi";

const OPEN = new Set(["requested", "approved", "exporting"]);
const TONES: Record<SelfHostMoveRequest["status"], Tone> = {
  requested: "info", approved: "info", exporting: "info", exported: "success",
  rejected: "warn", failed: "danger", cancelled: "neutral",
};

/** Ask the platform operator to move this space to its own server, and follow the request. */
export function SelfHostMoveCard({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const key = ["selfhost-move", makerspaceId];
  const [note, setNote] = useState("");
  const status = useQuery({ queryKey: key, queryFn: () => getSelfHostMove(makerspaceId) });
  const send = useMutation({
    mutationFn: () => requestSelfHostMove(makerspaceId, note.trim()),
    onSuccess: (data) => { client.setQueryData(key, data); setNote(""); },
  });
  if (status.isError) return <ErrorText resource={t`move request`} onRetry={() => { void status.refetch(); }} />;
  if (!status.isSuccess) return null;
  const current = status.data.request;
  const open = current ? OPEN.has(current.status) : false;
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`Moving takes the whole space to a server you run: inventory, members, history and settings. Staff and members keep their sign-in there. The platform operator reviews the request and runs the export; you do not download anything here.`}</p>
    {current ? <KeyValueCard title={t`Your move request`} items={[
      { label: t`Status`, value: <StatusPill tone={TONES[current.status]} label={current.status_label} /> },
      { label: t`Requested`, value: <RelativeTime date={current.requested_at} /> },
      ...(current.decision_note ? [{ label: t`Operator note`, value: current.decision_note }] : []),
    ]} /> : null}
    {open ? null : <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); send.mutate(); }}>
      <Field label={t`Note for the platform operator`} hint={t`Optional. For example, when you want to move.`}>
        <textarea className="desk-input min-h-20" maxLength={2000} value={note} onChange={(event) => setNote(event.target.value)} />
      </Field>
      <div><button type="submit" className="desk-button" disabled={send.isPending}>
        {send.isPending ? t`Sending…` : t`Request a move to self-host`}</button></div>
      {send.error ? <ErrorText message={send.error.message} /> : null}
    </form>}
  </div>;
}
