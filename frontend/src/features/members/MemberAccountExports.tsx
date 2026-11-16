import { formatDateTime, formatTime } from "../../lib/format";
import { Pagination, StatusPill } from "../../components/ui";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { accountKey, exportDownload, ownExports, requestExport } from "./memberAccountApi";
import { LogoLoader } from "../../components/LogoLoader";

const exportStatusLabel = (status: string) => {
  switch (status) {
    case "pending": return t`Queued`;
    case "running": return t`Preparing`;
    case "available": return t`Ready`;
    case "failed": return t`Failed`;
    default: return t`Unknown`;
  }
};
const exportStatusTone = (status: string) => (status === "available" ? "success" : status === "failed" ? "danger" : "warn");

export function MemberAccountExports({ makerspaceId }: { makerspaceId: number }) {
  const [page, setPage] = useState(1);
  const client = useQueryClient();
  const rows = useQuery({ queryKey: [...accountKey(makerspaceId), "exports", page], queryFn: () => ownExports(makerspaceId, page), retry: false,
    refetchInterval: (query) => query.state.data?.results.some((job) => ["pending", "running"].includes(job.status)) ? 5000 : false });
  const create = useMutation({ mutationFn: () => requestExport(makerspaceId), onSuccess: () => { setPage(1); void client.invalidateQueries({ queryKey: [...accountKey(makerspaceId), "exports"] }); } });
  const download = useMutation({ mutationFn: (id: string) => exportDownload(makerspaceId, id) });
  // Rendered inside the account page's Your data settings section, which owns the card and the heading.
  return <div className="grid min-w-0 gap-3">
    <p className="text-sm text-muted">{t`Download your profile, membership, history and payment records held by this makerspace as JSON in a ZIP. Export requests are limited to one per day. Files expire automatically.`}</p>
    <button type="button" className="desk-button-brand w-full sm:w-auto" disabled={create.isPending} onClick={() => create.mutate()}>{t`Request data export`}</button>
    {rows.isLoading ? <LogoLoader label={t`Loading exports…`} size={48} className="min-h-16 py-3" /> : null}
    {rows.error || create.error || download.error ? <p role="alert" className="text-sm text-danger">{(rows.error || create.error || download.error)?.message}</p> : null}
    {rows.data?.results.map((job) => <div key={job.id} className="border-t border-line pt-3"><p className="flex flex-wrap items-center gap-2 break-words text-sm text-ink">{t`Requested ${formatDateTime(job.created_at)}`}<StatusPill tone={exportStatusTone(job.status)} label={exportStatusLabel(job.status)} /></p>
      {job.status === "failed" ? <p role="alert" className="text-sm text-danger">{job.failure_detail}</p> : null}
      {job.status === "available" && new Date(job.expires_at).getTime() > Date.now() ? <button type="button" className="desk-button mt-2" disabled={download.isPending} onClick={() => download.mutate(job.id)}>{t`Prepare download link`}</button> : null}
    </div>)}
    {download.data ? <p className="flex flex-wrap items-center gap-3 text-sm text-muted"><a className="desk-button-primary w-full sm:w-auto" href={download.data.url} rel="noreferrer">{t`Download ZIP`}</a><span>{t`This link expires at ${formatTime(download.data.expires_at)}.`}</span></p> : null}
    <Pagination page={page} totalPages={rows.data?.next ? page + 1 : page} onChange={setPage} />
  </div>;
}
