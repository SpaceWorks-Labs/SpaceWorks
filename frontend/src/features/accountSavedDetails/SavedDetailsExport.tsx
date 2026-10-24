import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { getSessionGeneration } from "../../lib/api/sessionTokens";
import { downloadExport, exportStatus, requestExport, saveBlob } from "./api";
import { savedDetailsKey } from "./types";

export function SavedDetailsExport(props: { actorId: number }) {
  return <OwnerExport key={props.actorId} {...props} />;
}
function OwnerExport({ actorId }: { actorId: number }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const operationId = useRef(crypto.randomUUID()), mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const create = useMutation({ mutationFn: async () => {
    const session = getSessionGeneration("member"), job = await requestExport(operationId.current);
    if (!mounted.current || session !== getSessionGeneration("member")) throw new DOMException("The account changed.", "AbortError");
    return job;
  }, onSuccess: job => { setJobId(job.job_id); operationId.current = crypto.randomUUID(); } });
  const status = useQuery({ queryKey: [...savedDetailsKey(actorId), "export", jobId], queryFn: () => exportStatus(jobId!), enabled: Boolean(jobId), gcTime: 0, retry: false,
    refetchInterval: query => ["queued", "building"].includes(query.state.data?.state || "") && document.visibilityState === "visible" ? 3000 : false });
  const download = useMutation({ mutationFn: async () => {
    if (!jobId) return;
    const session = getSessionGeneration("member"), blob = await downloadExport(jobId);
    if (mounted.current && session === getSessionGeneration("member")) saveBlob(blob, "saved-details.zip");
  } });
  const error = create.error || status.error || download.error;
  const awaiting = Boolean(jobId) && (!status.data || ["queued", "building"].includes(status.data.state));
  return <div className="grid gap-3"><p>Your archive includes private saved values and your ready résumé files. Event submissions have separate owner exports. Archives expire after 24 hours.</p>
    <div className="flex flex-wrap gap-2"><button className="desk-button" disabled={create.isPending || awaiting} onClick={() => create.mutate()}>Create saved details archive</button>
      {status.data?.state === "ready" ? <button className="desk-button-primary" disabled={download.isPending} onClick={() => download.mutate()}>Download archive</button> : null}
      {jobId && status.error ? <button type="button" className="desk-button" onClick={() => void status.refetch()}>Retry archive status</button> : null}</div>
    {jobId && !status.data ? <p role="status">Archive: checking status</p> : null}
    {status.data ? <p role="status">Archive: {status.data.state}{status.data.expires_at ? " · expires " + new Date(status.data.expires_at).toLocaleString() : ""}</p> : null}
    {error && error.name !== "AbortError" ? <p role="alert" className="text-danger">{error.message}</p> : null}
  </div>;
}
