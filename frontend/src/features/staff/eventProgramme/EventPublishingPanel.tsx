import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { Card, Skeleton } from "../../../components/ui";
import { eventErrorText } from "../eventUi";
import { ShortLinkCard } from "../../events/shortLinks/ShortLinkCard";
import { PublishingQuestions, type Listing, type PageState } from "../eventPublishing/PublishingQuestions";
import { useProgrammeQuery, usePublishingSave, type Publishing } from "./api";
import { DirtySaveBar } from "./DirtySaveBar";
import { useOperationId } from "./useOperationId";
import { isProtectedDenial } from "./sessionScope";
import { useEvent, useUpdateEvent } from "../eventsApi";
import { signupAnswersFor, signupPatch, type SignupAnswers } from "../eventPublishing/SignupsQuestion";

/** L1 adds "who can find" and the page state; the generated type catches up at merge. */
type PublishingRow = Publishing & { listing?: Listing; page_state?: PageState };

export function EventPublishingPanel({ eventId, uploadsPending = false }: { eventId: number; uploadsPending?: boolean }) {
  const query = useProgrammeQuery<PublishingRow>(eventId, "publishing");
  const save = usePublishingSave(eventId);
  const [draft, setDraft] = useState<PublishingRow | null>(null);
  const [release, setRelease] = useState(false);
  const operationId = useOperationId();
  // Parity E-F3 (B2): spots, closing, the public count and approval are event fields, saved by the event PATCH.
  const event = useEvent(eventId);
  const updateEvent = useUpdateEvent(event.data?.makerspace_id ?? 0, eventId);
  const [signups, setSignups] = useState<SignupAnswers | null>(null);
  const signupBase = event.data ? signupAnswersFor(event.data) : null;
  const signupChanges = signups && signupBase ? signupPatch(signupBase, signups) : {};
  const signupsDirty = Object.keys(signupChanges).length > 0;
  const row = draft ?? query.data;
  const denied = [query.error, save.error].some(isProtectedDenial);
  useEffect(() => { if (denied) { setDraft(null); setRelease(false); } }, [denied]);
  if (denied) return <p role="alert" className="text-sm text-danger">{t`These publishing settings are no longer available for your access.`}</p>;
  const edit = (patch: Partial<PublishingRow>) => row && setDraft({ ...row, ...patch });
  const closed = row ? ["cancelled", "completed"].includes(row.status) : false;
  const published = row?.status === "published";
  const answers = row ? { is_public: row.is_public, listing: row.listing ?? "listed", page_state: row.page_state ?? "live",
    registration_audience: row.registration_audience } : null;
  const submit = () => {
    if (signupsDirty) updateEvent.mutate(signupChanges, { onSuccess: () => setSignups(null) });
    if (draft || release) savePublishing();
  };
  const savePublishing = () => row && answers && save.mutate({
    operation_id: operationId([row, release]), expected_version: row.version, is_public: row.is_public,
    registration_audience: row.registration_audience,
    // A private event is never listed: the server refuses `listing` while it is private.
    ...(row.is_public ? { listing: answers.listing } : {}), page_state: answers.page_state,
    ...(["draft", "published"].includes(row.status) ? { status: row.status } : {}),
    release_saved_website: release, ...(row.website_revision !== null ? { website_revision: row.website_revision } : {}),
  } as Partial<Publishing> & { operation_id: string; expected_version: number }, { onSuccess: () => { setDraft(null); setRelease(false); } });
  return <section className="grid gap-4" aria-label={t`Publishing`}><h3 className="title-section">{t`Three questions before sharing`}</h3>
    {query.isLoading ? <Skeleton className="h-36 w-full" /> : null}{query.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(query.error)}</p> : null}
    {row && answers ? <Card><div className="grid gap-4">
      <PublishingQuestions answers={answers} published={published} idPrefix={`publishing-${eventId}`} onChange={edit}
        signups={signups ?? signupBase ?? undefined} onSignupsChange={signupBase && !closed ? patch => setSignups({ ...(signups ?? signupBase), ...patch }) : undefined}
        approvalLocked={event.data?.status !== "draft"} />
      <label className="grid gap-1 text-sm font-semibold">{t`Publishing`}<select className="desk-input font-normal" value={row.status} disabled={closed} onChange={e => edit({ status: e.target.value as Publishing["status"] })}>
          <option value="draft">{t`Keep as a draft`}</option><option value="published">{t`Publish the event`}</option>
          {closed ? <option value={row.status}>{row.status}</option> : null}
        </select>
      </label>
      <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={release} disabled={row.website_revision === null || uploadsPending || save.isPending} onChange={e => setRelease(e.target.checked)} />{t`Release the currently saved website revision with this change`}</label>
      <p className="text-xs text-muted">{row.website_released ? t`Saving event settings does not release website drafts. Website: released.` : t`Saving event settings does not release website drafts. Website: draft.`}</p>
    </div></Card> : null}
    {row ? <ShortLinkCard eventId={eventId} published={published && row.is_public} /> : null}
    <DirtySaveBar dirty={Boolean(draft) || release || signupsDirty} pending={save.isPending || updateEvent.isPending} blocked={uploadsPending}
      error={save.error ? t`${eventErrorText(save.error)} Your edits are preserved. Reload and review the current version before retrying a conflict.` : updateEvent.error ? eventErrorText(updateEvent.error) : undefined}
      onDiscard={() => { setDraft(null); setRelease(false); setSignups(null); save.reset(); updateEvent.reset(); }} onSave={submit} />
  </section>;
}
