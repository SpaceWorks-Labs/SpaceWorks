import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorText } from "../../components/ui";
import { cutoutApi, cutoutKeys, eraserErrorText, type Cutout, type CutoutTarget } from "./api";
import { BoxArt } from "../../components/BoxSpinner";

const POLL_MS = 2000;
const working = (state?: Cutout["state"]) => state === "queued" || state === "running";

/**
 * "Remove background" for one holder's card photo (decision 314 c). Staff need card authority; a member acts on
 * their own card and must first agree that the photo is sent to the space's eraser service. Hidden when the
 * switch is off (the server answers 404) or no service is set up. The original is always kept.
 */
export function CutoutPanel({ target, photoSet = true, onChanged }: { target: CutoutTarget; photoSet?: boolean; onChanged?: () => void }) {
  const client = useQueryClient();
  const key = cutoutKeys.one(target);
  const [consent, setConsent] = useState(false);
  const query = useQuery({ queryKey: key, queryFn: () => cutoutApi.read(target), retry: false,
    refetchInterval: (state) => working(state.state.data?.state) ? POLL_MS : false });
  const update = (data: Cutout) => { client.setQueryData(key, data); onChanged?.(); };
  const queue = useMutation({ mutationFn: () => cutoutApi.queue(target, consent), onSuccess: update });
  const choose = useMutation({ mutationFn: (use: "cutout" | "original") => cutoutApi.choose(target, use), onSuccess: update });
  const discard = useMutation({ mutationFn: () => cutoutApi.discard(target), onSuccess: update });
  const optOut = useMutation({ mutationFn: (value: boolean) => cutoutApi.optOut(target, value), onSuccess: update });
  const data = query.data;
  if (query.isError || !data || !data.available) return null;
  const member = target.scope === "member";
  // Decision 345(b): members always see the processing notice and can opt out; an opted-out photo is never sent.
  const notice = member ? <EraserNotice data={data} busy={optOut.isPending} onChange={(value) => optOut.mutate(value)} /> : null;
  if (!photoSet || data.opted_out) {
    return notice ?? (data.opted_out ? <p className="text-sm text-muted">{t`This member opted out of background removal; their original photo is used.`}</p> : null);
  }
  const busy = queue.isPending || working(data.state);
  const error = queue.error ?? choose.error ?? discard.error;
  return <section className="grid gap-2" aria-label={t`Background eraser`}>
    {notice}
    <h3 className="text-sm font-semibold text-ink">{t`Remove the background`}</h3>
    <p className="text-sm text-muted">{member
      ? t`Your photo is sent to this space's eraser service to cut you out of the background. Your original photo is kept.`
      : t`The holder's photo is sent to the space's eraser service to cut them out of the background. The original is kept.`}</p>
    {member && data.state !== "done" ? <label className="flex min-h-11 items-start gap-2 text-sm text-ink">
      <input type="checkbox" className="mt-0.5 h-5 w-5" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
      <span>{t`I agree my photo is sent to the eraser service this space has set up.`}</span></label> : null}
    <p role="status" aria-live="polite" className="text-sm text-muted">
      {working(data.state) ? t`Removing the background…` : data.state === "failed" ? t`It didn't work: ${eraserErrorText(data.error_code)}`
        : data.state === "stale" ? t`The photo changed since. Run it again.` : ""}</p>
    {data.state === "done" && data.image_url ? <div className="grid gap-2">
      <img src={data.image_url} alt={t`The photo with the background removed`} className="h-40 w-auto max-w-full rounded-control border border-line bg-[repeating-conic-gradient(#d4d4d8_0_25%,#fff_0_50%)] bg-[length:16px_16px] object-contain" />
      <p className="text-sm text-ink">{data.use === "cutout" ? t`The card uses the cut-out.` : t`The card uses the original photo.`}</p>
    </div> : null}
    <div className="flex flex-wrap gap-2">
      {data.state === "done" ? <>
        {data.use === "original"
          ? <button type="button" className="desk-button-primary min-h-11" disabled={choose.isPending} onClick={() => choose.mutate("cutout")}>{t`Use cut-out`}</button>
          : <button type="button" className="desk-button min-h-11" disabled={choose.isPending} onClick={() => choose.mutate("original")}>{t`Use original`}</button>}
        <button type="button" className="desk-button-ghost min-h-11" disabled={discard.isPending} onClick={() => discard.mutate()}>{t`Discard cut-out`}</button>
      </> : null}
      <button type="button" className="desk-button min-h-11" disabled={busy || (member && !consent)} onClick={() => queue.mutate()}>
        {busy ? <><BoxArt size={16} mono />{t`Working…`}</> : data.state === "done" ? t`Run again` : t`Remove background`}</button>
    </div>
    {error ? <ErrorText message={error.message} /> : null}
  </section>;
}

/** The space's eraser notice and the member's opt-out switch (shown on the card photo upload). */
function EraserNotice({ data, busy, onChange }: { data: Cutout; busy: boolean; onChange: (optedOut: boolean) => void }) {
  return <div className="grid gap-2 rounded-control border border-line bg-surface p-3" role="note">
    <p className="text-sm text-ink">{data.notice}</p>
    <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
      <input type="checkbox" className="h-5 w-5" checked={Boolean(data.opted_out)} disabled={busy}
        onChange={(event) => onChange(event.target.checked)} />
      {t`Never send my photo to the background-removal service`}</label>
  </div>;
}
