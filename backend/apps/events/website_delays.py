"""Operational updates by durable identity; only selected versions change."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, ValidationError
from .event_permissions import PUBLISH_SCHEDULE
from .models_website import EventPage
from .website_copy import owner
from .website_revisions import operational_snapshot
from .website_revision_projection import snapshot_sessions


@transaction.atomic
def set_delay(target, slug, *, actor, minutes, revision=None, session_id=None):
    from .services_website import locked_target, bump, audit
    target, actor = locked_target(target, actor, PUBLISH_SCHEDULE)
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 0 <= minutes <= 1440:
        raise ValidationError({"delay_minutes": "Delay must be between zero and 1440 minutes."})
    page = EventPage.objects.select_for_update().filter(**owner(target)).first()
    if page is None:
        raise ValidationError("Create an occurrence override before changing its delays.")
    if revision is not None and revision != page.revision:
        raise ValidationError({"revision": "The page changed. Reload before changing delays."})
    alias = get_object_or_404(page.session_aliases, slug=slug)
    if session_id is not None and str(session_id) != str(alias.identity_id):
        raise ValidationError({"session_id": "The identity does not match this session path."})
    working = page.sessions.filter(identity_id=alias.identity_id).first()
    public_rows = snapshot_sessions(page.published_revision, public=True) if page.released and page.published_revision_id else []
    public = next((row for row in public_rows if row["session_id"] == str(alias.identity_id)), None)
    if working is None and public is None:
        raise NotFound()
    if working is not None:
        working.delay_minutes = minutes
        working.save(update_fields=["delay_minutes"])
        page.draft_revision = operational_snapshot(
            page, alias.identity_id, minutes, actor, source_revision=page.draft_revision)
        page.save(update_fields=["draft_revision"])
    if public is not None:
        page.published_revision = operational_snapshot(page, alias.identity_id, minutes, actor)
        page.save(update_fields=["published_revision"])
    bump(page)
    audit(page, actor, "event.website_delay_changed", session_id=str(alias.identity_id), delay_minutes=minutes,
          revision=page.revision)
    return target
