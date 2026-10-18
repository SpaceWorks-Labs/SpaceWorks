import { useEffect, useState } from "react";
import { Card, Skeleton } from "../../../components/ui";
import { eventErrorText } from "../eventUi";
import { useProgrammeQuery, usePublishingSave, type Publishing } from "./api";
import { DirtySaveBar } from "./DirtySaveBar";
import { useOperationId } from "./useOperationId";
import { isProtectedDenial } from "./sessionScope";

export function EventPublishingPanel({ eventId, uploadsPending = false }: { eventId: number; uploadsPending?: boolean }) {
  const query = useProgrammeQuery<Publishing>(eventId, "publishing");
  const save = usePublishingSave(eventId);
  const [draft, setDraft] = useState<Publishing | null>(null);
  const [release, setRelease] = useState(false);
  const operationId = useOperationId();
  const row = draft ?? query.data;
  const denied = [query.error, save.error].some(isProtectedDenial);
  useEffect(() => { if (denied) { setDraft(null); setRelease(false); } }, [denied]);
  if (denied) return <p role="alert" className="text-sm text-danger">These publishing settings are no longer available for your access.</p>;
  const edit = (patch: Partial<Publishing>) => row && setDraft({ ...row, ...patch });
  return <section className="grid gap-4" aria-label="Publishing"><h3 className="title-section">Three questions before sharing</h3>
    {query.isLoading ? <Skeleton className="h-36 w-full" /> : null}{query.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(query.error)}</p> : null}
    {row ? <Card><div className="grid gap-4">
      <label className="grid gap-1 text-sm font-semibold">Who can see?<select className="desk-input font-normal" value={row.is_public ? "public" : "private"} onChange={e => edit({ is_public: e.target.value === "public" })}><option value="private">Private event</option><option value="public">Public event</option></select></label>
      <label className="grid gap-1 text-sm font-semibold">Who can find?<select className="desk-input font-normal" value={row.status} disabled={["cancelled", "completed"].includes(row.status)} onChange={e => edit({ status: e.target.value as Publishing["status"] })}><option value="draft">Keep in draft</option><option value="published">Publish event listing</option>{["cancelled", "completed"].includes(row.status) ? <option value={row.status}>{row.status}</option> : null}</select></label>
      <label className="grid gap-1 text-sm font-semibold">Can people sign up?<select className="desk-input font-normal" value={row.registration_audience} onChange={e => edit({ registration_audience: e.target.value })}><option value="accounts">Signed-in accounts</option><option value="members">Members</option><option value="participating_organizations">Selected organizations</option><option value="invite">Invitation only</option></select></label>
      <p className="text-sm text-muted">{row.is_public ? "Public" : "Private"} · {row.status} · {row.registration_audience.replace(/_/g, " ")}. Website: {row.website_released ? "released" : "draft"}.</p>
      <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={release} disabled={row.website_revision === null || uploadsPending || save.isPending} onChange={e => setRelease(e.target.checked)} />Release the currently saved website revision with this change</label>
      <p className="text-xs text-muted">Saving event settings does not release website drafts. Directory eligibility follows makerspace publication settings.</p>
    </div></Card> : null}
    <DirtySaveBar dirty={Boolean(draft) || release} pending={save.isPending} blocked={uploadsPending} error={save.error ? `${eventErrorText(save.error)} Your edits are preserved. Reload and review the current version before retrying a conflict.` : undefined} onDiscard={() => { setDraft(null); setRelease(false); save.reset(); }} onSave={() => row && save.mutate({ operation_id: operationId([row, release]), expected_version: row.version, is_public: row.is_public, registration_audience: row.registration_audience, ...(["draft", "published"].includes(row.status) ? { status: row.status } : {}), release_saved_website: release, ...(row.website_revision !== null ? { website_revision: row.website_revision } : {}) }, { onSuccess: () => { setDraft(null); setRelease(false); } })} />
  </section>;
}
