import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Callout } from "../../components/ui";
import { memberRequest, StructuredApiError } from "../../lib/api";
import type { IceServer, Signal, Watch } from "../staff/panels/machine/adapters/adaptersApi";
import { WatchViewer, type WatchTransport } from "../staff/panels/machine/adapters/WatchViewer";
import { BoxArt } from "../../components/BoxSpinner";

const post = (path: string, body?: unknown) => memberRequest<never>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

/** "Watch my job": the member whose request is running may watch their own machine for five minutes. The server answers 404 when the machine has no camera. */
export function MemberJobWatch({ jobId }: { jobId: number }) {
  const [watch, setWatch] = useState<Watch | null>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { if (!watch) return; const timer = window.setInterval(() => setNow(Date.now()), 1_000); return () => window.clearInterval(timer); }, [watch]);
  const start = useMutation({ mutationFn: () => post(`/member/adapter-watch/requests/${jobId}`) as Promise<Watch>, onSuccess: row => setWatch(row) });
  const stop = useMutation({ mutationFn: () => memberRequest<Watch>(`/member/adapter-watch/${watch!.id}`, { method: "DELETE" }), onSuccess: () => setWatch(null) });
  const remaining = watch ? Math.max(0, Math.floor((new Date(watch.expires_at).getTime() - now) / 1_000)) : 0;
  const open = watch !== null && remaining > 0;
  const transport: WatchTransport | null = watch ? {
    poll: after => memberRequest<{ signals: Signal[]; ice_servers: IceServer[] }>(`/member/adapter-watch/${watch.id}/signal?after=${after}`),
    signal: body => post(`/member/adapter-watch/${watch.id}/signal`, body),
    frame: () => memberRequest<{ content_type: string | null; data: string | null }>(`/member/adapter-watch/${watch.id}/frame`),
  } : null;
  const missing = start.error instanceof StructuredApiError && start.error.status === 404;
  return <section className="desk-panel grid gap-3 p-5" aria-label={t`Watch my job`}>
    <h2 className="title-panel">{t`Watch my job`}</h2>
    <p className="text-sm text-muted">{t`See your machine while it works. The camera only sends while you are watching, a watch lasts five minutes, and staff can see in the audit log that you watched.`}</p>
    {open && transport ? <>
      <WatchViewer transport={transport} label={t`Camera view of your machine`} />
      <p className="text-sm text-muted" role="status">{t`Closes in ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}`}</p>
      <button type="button" className="desk-button justify-self-start" disabled={stop.isPending} onClick={() => stop.mutate()}>{t`Stop watching`}</button>
    </> : <button type="button" className="desk-button-primary justify-self-start" disabled={start.isPending} onClick={() => start.mutate()}>{start.isPending ? <><BoxArt size={16} mono />{t`Starting…`}</> : t`Watch my job`}</button>}
    {missing ? <Callout size="inline" tone="warn" lead={t`No camera to show.`} body={t`This machine has no camera that can be watched right now.`} />
      : start.isError || stop.isError ? <p role="alert" className="text-sm text-danger">{(start.error ?? stop.error)?.message}</p> : null}
  </section>;
}
