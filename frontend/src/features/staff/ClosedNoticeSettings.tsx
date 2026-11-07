import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";

type ClosedNotice = { public_closed_notice: string; public_reopens_on: string | null };

/**
 * #77: the Space Manager's "closed for now" banner. Text and an optional reopening date;
 * the space keeps working. Shown only while `public_site.closed_notice` is on.
 */
export function ClosedNoticeSettings({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const path = `/admin/makerspace/${makerspaceId}/public-closed-notice`;
  const query = useQuery({ queryKey: ["closed-notice", makerspaceId], retry: false, queryFn: () => staffRequest<ClosedNotice>(path) });
  const [draft, setDraft] = useState<ClosedNotice | null>(null);
  useEffect(() => { setDraft(null); }, [query.data]);
  const save = useMutation({
    mutationFn: (body: ClosedNotice) => staffRequest<ClosedNotice>(path, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: data => {
      client.setQueryData(["closed-notice", makerspaceId], data);
      for (const key of ["tenant-bootstrap", "runtime-tenant", "runtime-tenant-origin"]) void client.invalidateQueries({ queryKey: [key] });
    },
  });
  const value = draft ?? query.data;
  if (!value) return query.error ? <p role="alert" className="text-sm text-danger">{query.error.message}</p> : null;
  const id = `closed-notice-${makerspaceId}`;
  return <fieldset className="grid gap-3 rounded-xl border border-line p-4">
    <legend className="px-1 text-sm font-semibold">{t`Closed-for-now banner`}</legend>
    <p className="text-xs text-muted">{t`Shown at the top of the public page. Everything keeps working; leave the text empty to hide it.`}</p>
    <label htmlFor={id} className="text-sm font-semibold">{t`Notice`}</label>
    <textarea id={id} className="desk-input min-h-20" maxLength={280} value={value.public_closed_notice}
      onChange={event => setDraft({ ...value, public_closed_notice: event.target.value })} />
    <label className="grid gap-1 text-sm font-semibold">{t`Reopening date (optional)`}<input type="date" className="desk-input max-w-xs font-normal" value={value.public_reopens_on ?? ""}
        onChange={event => setDraft({ ...value, public_reopens_on: event.target.value || null })} />
    </label>
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button-primary" disabled={!draft || save.isPending} onClick={() => draft && save.mutate(draft)}>{save.isPending ? t`Saving…` : t`Save banner`}</button>
      {draft ? <button type="button" className="desk-button" onClick={() => setDraft(null)}>{t`Discard`}</button> : null}
    </div>
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
  </fieldset>;
}
