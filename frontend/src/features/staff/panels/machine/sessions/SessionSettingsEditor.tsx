import { useEffect, useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchSessionSettings, saveSessionSettings, sessionErrorMessage, sessionKeys } from "../../../../machine-sessions/api";
import { errorCode } from "../machineJobsApi";

const READ_ONLY: Record<string, string> = {
  setting_not_delegated: "Only the Space Manager, or a manager they have handed this setting to, can change it.",
  setting_locked: "The Space Manager has locked this setting, so only they can change it.",
};

/** Per-type machine-session setting (#158.5): how long a session may run before it stops itself. */
export function SessionSettingsEditor({ makerspaceId, machineTypeId, visible = true }: { makerspaceId: number; machineTypeId: number; visible?: boolean }) {
  const id = useId();
  const client = useQueryClient();
  const query = useQuery({ queryKey: sessionKeys.settings(makerspaceId, machineTypeId), enabled: visible,
    queryFn: () => fetchSessionSettings(makerspaceId, machineTypeId) });
  const save = useMutation({ mutationFn: (minutes: number) => saveSessionSettings(makerspaceId, machineTypeId, minutes),
    onSuccess: data => client.setQueryData(sessionKeys.settings(makerspaceId, machineTypeId), data) });
  const [minutes, setMinutes] = useState("");
  useEffect(() => { if (query.data) setMinutes(String(query.data.session_max_minutes)); }, [query.data]);
  if (!visible) return null;
  const lock = READ_ONLY[errorCode(save.error) ?? ""];
  return <section className="rounded-xl border border-line bg-panel p-3" aria-labelledby={`${id}-title`}>
    <h3 id={`${id}-title`} className="title-panel">Machine sessions</h3>
    <p className="my-2 text-sm text-muted">A session nobody stops ends by itself after this long, at check-out or at closing time, and waits for a staff check.</p>
    {query.isLoading ? <p role="status">Loading session settings…</p> : null}
    {query.data ? <form className="flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); save.mutate(Number(minutes)); }}>
      <label className="grid gap-1 text-sm">Longest session (minutes)
        <input className="desk-input w-40" type="number" min={5} max={1440} required value={minutes}
          onChange={event => setMinutes(event.target.value)} disabled={save.isPending || Boolean(lock)} /></label>
      {!lock ? <button className="desk-button-primary" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save"}</button> : null}
    </form> : null}
    {save.isSuccess ? <p role="status" className="mt-2 text-sm">Session setting saved.</p> : null}
    {lock ? <p role="status" className="mt-2 text-sm">{lock}</p> : null}
    {query.error ? <p role="alert" className="mt-2 text-sm text-danger">{sessionErrorMessage(query.error)}</p> : null}
    {save.error && !lock ? <p role="alert" className="mt-2 text-sm text-danger">{sessionErrorMessage(save.error)}</p> : null}
  </section>;
}
