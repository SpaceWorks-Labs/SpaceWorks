import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { accountKey, exportDownload, ownExports, requestExport } from "./memberAccountApi";

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
    {rows.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading exports…`}</p> : null}
    {rows.error || create.error || download.error ? <p role="alert" className="text-sm text-danger">{(rows.error || create.error || download.error)?.message}</p> : null}
    {rows.data?.results.map((job) => <div key={job.id} className="border-t border-line pt-3"><p className="break-words text-sm text-ink">{t`Requested ${new Date(job.created_at).toLocaleString(formatLocale())} · ${job.status}`}</p>
      {job.status === "failed" ? <p role="alert" className="text-sm text-danger">{job.failure_detail}</p> : null}
      {job.status === "available" && new Date(job.expires_at).getTime() > Date.now() ? <button type="button" className="desk-button mt-2" disabled={download.isPending} onClick={() => download.mutate(job.id)}>{t`Prepare download link`}</button> : null}
    </div>)}
    {download.data ? <p className="flex flex-wrap items-center gap-3 text-sm text-muted"><a className="desk-button-primary w-full sm:w-auto" href={download.data.url} rel="noreferrer">{t`Download ZIP`}</a> {t` Link expires ${new Date(download.data.expires_at).toLocaleTimeString(formatLocale())}.`}</p> : null}
    <div className="flex flex-wrap gap-2"><button type="button" className="desk-button" disabled={!rows.data?.previous} onClick={() => setPage(page - 1)}>{t`Previous exports`}</button><button type="button" className="desk-button" disabled={!rows.data?.next} onClick={() => setPage(page + 1)}>{t`Next exports`}</button></div>
  </div>;
}
