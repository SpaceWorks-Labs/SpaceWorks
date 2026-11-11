"""Publishing questions wrap the existing event/page workflows, never raw status writes."""

from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.events import event_authority, services
from apps.events.event_permissions import EDIT_DETAILS, PUBLISH_SCHEDULE
from apps.events.website_visibility import effective_page

from .commands import ProgrammeUnavailable, event_version, execute_command
from .aggregate import aggregate


PUBLISHING_FIELDS = ("is_public", "listing", "page_state", "registration_audience")


def _answers(event):
    """The three questions plus the page state, as the audit row records them."""
    return {"is_public": event.is_public, "listing": event.listing, "page_state": event.page_state,
            "registration_audience": event.registration_audience}


def project_publishing(event, *, actor):
    event_authority.require(actor, event, EDIT_DETAILS)
    page = effective_page(event)
    return {**aggregate(event, actor), "is_public": event.is_public,
            "listing": event.listing, "page_state": event.page_state,
            "registration_audience": event.registration_audience, "status": event.status,
            "website_released": bool(page and page.released),
            "website_revision": page.revision if page else None}


def save_publishing(event, *, actor, data):
    def apply(locked, locked_actor):
        before = event_version(locked)
        requested = data.get("status", locked.status)
        if requested == "draft" and locked.status != "draft":
            raise ValidationError({"status": gettext("A published event cannot return to draft.")})
        if "listing" in data and not data.get("is_public", locked.is_public):
            raise ValidationError({"listing": gettext("A private event is never listed; make it visible first.")})
        changes = {key: data[key] for key in PUBLISHING_FIELDS if key in data}
        if changes:
            previous = _answers(locked)
            locked = services.update_event(locked, actor=locked_actor, **changes)
            current = _answers(locked)
            moved = sorted(key for key in PUBLISHING_FIELDS if current[key] != previous[key])
            if moved:
                audit.record(locked_actor, "event.publishing_changed", makerspace=locked.makerspace, target=locked,
                             meta={"event_id": locked.pk, "changed_fields": moved,
                                   "before": previous, "after": current})
        publish = requested == "published" and locked.status != "published"
        release = data.get("release_saved_website", False)
        if publish:
            event_authority.require(locked_actor, locked, PUBLISH_SCHEDULE)
            locked = services.publish(locked, actor=locked_actor, publish_website=release,
                                      website_revision=data.get("website_revision"),
                                      publish_without_room=data.get("publish_without_room", False))
        elif release:
            from apps.events.services_website import set_release_locked
            set_release_locked(locked, actor=locked_actor, released=True, revision=data["website_revision"])
        # G owns the aggregate version writer, including lifecycle/release integration.
        # Fail closed until installed; never fake a version or silently lose CAS.
        if (changes or publish or release) and event_version(locked) <= before:
            raise ProgrammeUnavailable("event_version_writer_unavailable", "Event version writer integration is required.")
        return project_publishing(locked, actor=locked_actor)

    return execute_command(event=event, actor=actor, command="publishing", payload=data,
                           expected_version=data["expected_version"], operation_id=data["operation_id"],
                           execute=apply, permission=EDIT_DETAILS)
