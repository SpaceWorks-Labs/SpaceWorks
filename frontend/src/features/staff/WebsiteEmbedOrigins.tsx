import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";

export function WebsiteEmbedOrigins({ makerspaceId }: { makerspaceId: number }) {
  const key = ["website-embed-origins", makerspaceId];
  const path = `/admin/makerspaces/${makerspaceId}/website-embed-origins/`;
  const client = useQueryClient();
  const query = useQuery({ queryKey: key, queryFn: async () => {
    const data = await staffRequest<{ origins: string[] }>(path);
    if (!Array.isArray(data.origins) || data.origins.some((value) => typeof value !== "string")) throw new Error(t`Embed settings are unavailable.`);
    return data;
  } });
  const [origins, setOrigins] = useState("");
  useEffect(() => { if (query.data) setOrigins(query.data.origins.join("\n")); }, [query.data]);
  const save = useMutation({ mutationFn: () => staffRequest(path, { method: "PUT", body: JSON.stringify({ origins: origins.split("\n").map((row) => row.trim()).filter(Boolean) }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
  return <form className="grid gap-2 border-t border-line pt-4" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
    <label className="grid gap-2 text-sm font-semibold text-ink">{t`Website embed origins`}<textarea className="desk-input w-full min-w-0 font-normal" rows={3} value={origins} onChange={(e) => setOrigins(e.target.value)} disabled={query.isLoading || Boolean(query.error)} /></label>
    <p className="text-sm text-muted">{t`One exact HTTPS origin per line, for example https://partner.example. No paths or wildcards. Empty disables embeds. Each domain's website and embed features must also be enabled.`}</p>
    {query.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading embed settings…`}</p> : null}
    {query.error || save.error ? <p role="alert" className="text-sm text-danger">{(query.error || save.error)?.message}</p> : null}
    {query.error ? <button className="desk-button w-fit" type="button" onClick={() => query.refetch()}>{t`Retry embed settings`}</button> : null}
    <button className="desk-button-primary w-fit" type="submit" disabled={query.isLoading || Boolean(query.error) || save.isPending}>{save.isPending ? t`Saving…` : t`Save embed origins`}</button>
    {save.isSuccess ? <p role="status" className="text-sm text-success-ink">{t`Embed origins saved.`}</p> : null}
  </form>;
}
