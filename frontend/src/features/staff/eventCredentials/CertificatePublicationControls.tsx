import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";

type Policy = { enabled: boolean; event_version: number };

export function CertificatePublicationControls({ eventId }: { eventId: number }) {
  const path = `/admin/events/${eventId}/certificates/verification-policy/`;
  const query = useQuery({ queryKey: ["event-certificate-publication", eventId], queryFn: () => staffRequest<Policy>(path), retry: false });
  const [enabled, setEnabled] = useState(false);
  const [ids, setIds] = useState("");
  const [dirty, setDirty] = useState(false);
  useEffect(() => { if (query.data && !dirty) setEnabled(query.data.enabled); }, [query.data, dirty]);
  const parts = ids.trim() ? ids.split(",").map((value) => value.trim()) : [];
  const valid = parts.length <= 200 && parts.every((value) => /^[1-9]\d*$/.test(value)) && new Set(parts).size === parts.length;
  const apply = useMutation({ mutationFn: () => staffRequest<Policy>(path, { method: "POST", body: JSON.stringify({
    operation_id: crypto.randomUUID(), expected_version: query.data?.event_version, enabled, certificate_ids: parts.map(Number),
  }) }), onSuccess: async () => { setDirty(false); setIds(""); await query.refetch(); } });
  const error = query.error || apply.error;
  return <fieldset className="mt-3 grid gap-3 border-t border-line pt-3" disabled={!query.data || apply.isPending}>
    <legend className="text-sm font-semibold text-ink">{t`Certificate publication policy`}</legend>
    <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={enabled} onChange={(event) => { setDirty(true); setEnabled(event.target.checked); }} />{t`Allow event/date/status public verification for this event`}</label>
    <label className="grid gap-1 text-sm">{t`Optional existing certificate IDs (comma-separated, up to 200)`}<input className="desk-input" value={ids} onChange={(event) => setIds(event.target.value)} /></label>
    <p className="text-xs text-muted">{t`Historical certificates stay private until selected here. Applying the checked policy opts selected issued or revoked certificates in. Withdrawing the event policy immediately hides all verification. PDFs stay private, and a recipient's name shows only if they choose.`}</p>
    <button type="button" className="desk-button" disabled={!valid || apply.isPending} onClick={() => apply.mutate()}>{t`Apply verification policy`}</button>
    {apply.isSuccess ? <p role="status" className="text-sm text-success-ink">{t`Verification policy saved.`}</p> : null}
    {!valid ? <p role="alert" className="text-sm text-danger">{t`Enter up to 200 unique numeric certificate IDs.`}</p> : null}
    {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
  </fieldset>;
}
