"""Speaker history: the one answer to "which events did this account speak at here".

`contributions_for(user, makerspace)` is a frozen export: the public-profile backend
imports it lazily and reads only `event`, `occurred_at` and `role` from each item. Keep that
signature and those attributes stable.

Rules (query-derived on every call, so a removal or correction is reflected immediately):

- only account-linked, not-removed `EventSpeaker` rows count -- never an email or a name;
- only events that were released to the public lifecycle: PUBLISHED or COMPLETED (a draft
  was never announced, a cancelled one never happened);
- only once the session has started: `occurred_at` is the earliest linked website session
  start, falling back to the event start, and it must be in the past;
- provenance like member_history: the event's HOST is `makerspace`, the host is servable
  and still exposes the events module. A collaborator space does not inherit the credit.

Whether a title may be shown publicly is the CALLER's decision (`event.is_public`); this
module answers "did it happen", not "may a stranger see it".
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SpeakerContribution:
    event: object
    occurred_at: datetime
    role: str
    speaker_id: int


def speaking_rows(user, makerspace):
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable

    from .models import Event, EventSpeaker

    if user is None or not getattr(user, "pk", None) or makerspace is None:
        return EventSpeaker.objects.none()
    if not module_enabled(makerspace, "events") or not is_servable(makerspace):
        return EventSpeaker.objects.none()
    return (EventSpeaker.objects.filter(
        user_id=user.pk, removed_at__isnull=True, event__makerspace_id=makerspace.pk,
        event__status__in=(Event.Status.PUBLISHED, Event.Status.COMPLETED),
    ).select_related("event", "section").order_by("-event__starts_at", "-pk"))


def _occurred_at(speaker):
    from datetime import timedelta
    from .website_visibility import effective_page
    from .website_revision_projection import snapshot_sessions

    page = effective_page(speaker.event)
    if speaker.section_id and page and page.released and page.published_revision_id:
        revision = page.published_revision
        # Link by the retained, page-owned section, never by a display name/email.
        if speaker.section.page_id == page.pk:
            starts = [datetime.fromisoformat(row["starts_at"]) for row in
                      snapshot_sessions(revision, public=True)
                      if speaker.section.slug in row["speakers"]]
            if starts:
                shift = speaker.event.starts_at - revision.source_anchor_start if page.series_id else timedelta()
                return min(starts) + shift
    return speaker.event.starts_at


def contributions_for(user, makerspace, *, now=None):
    """Iterable of SpeakerContribution(event, occurred_at, role) newest first."""
    from django.utils import timezone

    now = now or timezone.now()
    result = []
    for speaker in speaking_rows(user, makerspace):
        occurred = _occurred_at(speaker)
        if occurred <= now:
            result.append(SpeakerContribution(speaker.event, occurred, "speaker", speaker.pk))
    return sorted(result, key=lambda row: (row.occurred_at, row.speaker_id), reverse=True)
