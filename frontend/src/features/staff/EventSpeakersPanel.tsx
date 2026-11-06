import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ConfirmDialog, StatusPill } from "../../components/ui";
import type { Tone } from "../../components/ui/types";
import { EventPanelPager } from "./EventPanelPager";
import { AssignSpeakerForm, InviteSpeakerForm, type SpeakerSection } from "./EventSpeakerForms";
import { useEventSpeakers, useRemoveSpeaker, type EventSpeaker } from "./eventSpeakersApi";
import { useEventWebsite } from "./eventWebsiteApi";
import { panelEmpty, panelRow } from "./eventPanelStyles";
import { eventErrorText } from "./eventUi";

const STATUS: Record<EventSpeaker["status"], { label: string; tone: Tone }> = {
  linked: { label: t`Linked`, tone: "success" },
  invited: { label: t`Invited`, tone: "warn" },
  removed: { label: t`Removed`, tone: "neutral" },
};

function speakerMeta(row: EventSpeaker) {
  const parts = [row.user ? `Account: ${row.user.display_name}` : row.claim_expires_at ? `Claim link expires ${new Date(row.claim_expires_at).toLocaleString(formatLocale())}` : "Not yet claimed"];
  if (row.linked_via === "claimed") parts.push("Claimed the link");
  if (row.section_slug) parts.push(`Website profile: ${row.section_slug}`);
  if (row.grants_check_in && row.status !== "removed") parts.push("Can check people in");
  return parts.join(" · ");
}

/** The website's speaker sections, so a speaker can be tied to their public profile. */
function useSpeakerSections(eventId: number, makerspaceId: number, websiteEnabled: boolean): SpeakerSection[] {
  const website = useEventWebsite({ kind: "events", id: eventId, makerspaceId }, websiteEnabled);
  return (website.data?.sections ?? []).filter((row) => row.kind === "speaker").map((row) => ({ slug: row.slug, title: row.title }));
}

/** Who speaks at this event. A linked speaker shows the event on their history; check-in is an opt-in extra. */
export function EventSpeakersPanel({ eventId, makerspaceId, websiteEnabled, disabled = false }: {
  eventId: number; makerspaceId: number; websiteEnabled: boolean; disabled?: boolean;
}) {
  const [page, setPage] = useState(1);
  const speakers = useEventSpeakers(eventId, page);
  const remove = useRemoveSpeaker(eventId);
  const sections = useSpeakerSections(eventId, makerspaceId, websiteEnabled);
  const [removing, setRemoving] = useState<EventSpeaker | null>(null);
  const rows = speakers.data?.results ?? [];
  return <section className="grid gap-4" aria-label={t`Event speakers`}>
    <div><h3 className="title-section">{t`Speakers`}</h3>
      <p className="mt-1 text-sm text-muted">{t`Link speakers to their accounts so the talk appears in their event history. Removing a speaker leaves their separate Team check-in grant active. Revoke check-in access on the Team tab.`}</p></div>
    {!disabled ? <div className="grid gap-4 lg:grid-cols-2">
      <AssignSpeakerForm eventId={eventId} sections={sections} disabled={disabled} />
      <InviteSpeakerForm eventId={eventId} sections={sections} disabled={disabled} />
    </div> : null}
    {speakers.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(speakers.error)}</p> : null}
    {remove.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(remove.error)}</p> : null}
    {speakers.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading speakers…`}</p> : null}
    {speakers.isSuccess && !rows.length ? <p className={panelEmpty}>{t`No speakers yet. Assign an account or create a claim link.`}</p> : null}
    {rows.length ? <ul className="grid gap-3" aria-label={t`Speakers`}>{rows.map((row) => <li key={row.id} className={panelRow}>
      <div className="min-w-0"><p className="title-section break-words">{row.display_name}</p>
        <p className="mt-1 text-sm text-muted [overflow-wrap:anywhere]">{speakerMeta(row)}</p></div>
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill label={STATUS[row.status]?.label ?? row.status} tone={STATUS[row.status]?.tone ?? "neutral"} />
        {row.status !== "removed" && !disabled ? <button className="desk-button-danger-outline" type="button" disabled={remove.isPending} onClick={() => { remove.reset(); setRemoving(row); }}>{t`Remove ${row.display_name}`}</button> : null}
      </div>
    </li>)}</ul> : null}
    <EventPanelPager page={page} setPage={setPage} previous={speakers.data?.previous} next={speakers.data?.next} />
    <ConfirmDialog open={removing !== null} title={t`Remove speaker`} tone="danger" confirmLabel={t`Remove speaker`} pending={remove.isPending}
      message={t`Remove ${removing?.display_name ?? "this speaker"} from the event? An unclaimed link stops working. Their separate Team check-in grant stays active; revoke check-in access on the Team tab.`}
      onCancel={() => setRemoving(null)} onConfirm={() => { if (removing) remove.mutate(removing.id, { onSettled: () => setRemoving(null) }); }} />
  </section>;
}
