"""Locked, audited content writes; all callers recheck live event authority."""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit.services import record
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.resource_clone import clone_transaction

from . import event_authority
from .event_permissions import EDIT_DETAILS, PUBLISH_SCHEDULE
from .feature_gates import require_feature
from .models import Event, EventSeries
from .models_website import EventPage, EventPageSection, EventSession, EventSessionSpeaker
from .serializers_website import WebsiteContentInput
from .staff_grant_locks import lock_authority
from .website_copy import copy_page, owner
from .website_projection import window
from .website_content import PAGE_FIELDS, SECTION_FIELDS, SECTION_DETAIL_DEFAULTS


def locked_target(target, actor, permission):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(target.makerspace_id)
    if isinstance(target, Event):
        series_id = Event.objects.values_list("series_id", flat=True).get(pk=target.pk)
        if series_id:
            EventSeries.objects.select_for_update().get(pk=series_id)
    target = type(target).objects.select_for_update().get(pk=target.pk)
    target.makerspace = require_module_locked(target.makerspace, "events")
    actor = lock_authority(actor, target)
    event_authority.require(actor, target, permission)
    require_feature(target, "events.website")
    if target.status in {"cancelled", "completed"}:
        raise ValidationError("Terminal events are read-only.")
    return target, actor


def audit(page, actor, action, **meta):
    record(actor=actor, action=action, makerspace=page.makerspace, target=page, meta=meta)


def own_page(target, copies, asset_map=None):
    page = EventPage.objects.select_for_update().filter(**owner(target)).first()
    if page is not None:
        return page
    if isinstance(target, Event) and target.series_id:
        page = copy_page(target, target, copies=copies, preserve_delays=True,
                         preserve_revision=True, asset_map=asset_map)
    return page or EventPage.objects.create(makerspace=target.makerspace, **owner(target))


def bump(page):
    page.revision += 1
    page.save(update_fields=["revision", "released", "updated_at"])


def _validate_content(target, data, assets):
    sections = {row["slug"]: row for row in data["sections"]}
    if len(sections) != len(data["sections"]):
        raise ValidationError("Section slugs must be unique.")
    if any(row["asset_id"] is not None and row["asset_id"] not in assets for row in sections.values()):
        raise ValidationError("Images must belong to this page.")
    slugs = set()
    start, end = window(target)
    if isinstance(target, EventSeries) and data["sessions"]:
        from django.db.models import F
        duration = max(row["ends_at"] - start for row in data["sessions"])
        if target.occurrences.filter(website_page__isnull=True).alias(
            website_duration=F("ends_at") - F("starts_at"),
        ).filter(website_duration__lt=duration).exists():
            raise ValidationError("The programme exceeds an inheriting occurrence's window. Create its occurrence override first.")
    for session in data["sessions"]:
        if session["slug"] in slugs:
            raise ValidationError("Session slugs must be unique.")
        slugs.add(session["slug"])
        if not start <= session["starts_at"] < session["ends_at"] <= end:
            raise ValidationError("Sessions must lie inside the event window.")
        if len(session["speakers"]) != len(set(session["speakers"])):
            raise ValidationError("A speaker can appear only once per session.")
        for kind, names in (("track", [session["track"]]), ("room", [session["room"]]),
                            ("speaker", session["speakers"])):
            if any(name is not None and (name not in sections or sections[name]["kind"] != kind) for name in names):
                raise ValidationError(f"Choose {kind} sections from this page.")


def save_content(target, *, actor, data):
    serializer = WebsiteContentInput(data=data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with clone_transaction() as copies:
        from .event_permissions import VIEW
        target, actor = locked_target(target, actor, VIEW)
        if not (event_authority.can(actor, target, EDIT_DETAILS) or event_authority.can(actor, target, PUBLISH_SCHEDULE)):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        existing = EventPage.objects.filter(**owner(target)).first()
        from .website_projection import project
        if data["revision"] != project(target)["revision"]:
            raise ValidationError({"revision": "The page changed. Reload before saving."})
        before = project(target)
        # An older full-content client must not erase newly added editorial fields.
        previous = {row["slug"]: row for row in before["sections"]}
        for row in data["sections"]:
            for key, default in SECTION_DETAIL_DEFAULTS.items():
                row.setdefault(key, previous.get(row["slug"], {}).get(key, default))
        section_fields = (*SECTION_FIELDS, "asset_id")
        if ([{key: row[key] for key in section_fields} for row in before["sections"]] != data["sections"]
                or any(data[key] != before[key] for key in PAGE_FIELDS if key in data)):
            event_authority.require(actor, target, EDIT_DETAILS)
        remapped = {}
        page = own_page(target, copies, asset_map=remapped)
        # Resolve exact inherited asset IDs, including renamed/new sections.
        if existing is None and remapped:
            for row in data["sections"]:
                if row["asset_id"] is not None:
                    if row["asset_id"] not in remapped:
                        raise ValidationError("Images must belong to the inherited page.")
                    row["asset_id"] = remapped[row["asset_id"]]
        assets = set(page.assets.values_list("pk", flat=True))
        _validate_content(target, data, assets)
        # Schedule fields belong to publish_schedule; detail editors cannot smuggle them.
        if not event_authority.can(actor, target, PUBLISH_SCHEDULE):
            current = project(target)["sessions"]
            fields = ("slug", "title", "body", "starts_at", "ends_at", "track", "room", "speakers", "visibility")
            if [{key: row[key] for key in fields} for row in current] != data["sessions"]:
                raise ValidationError("Schedule changes require publish_schedule.")
        delays = dict(page.sessions.values_list("slug", "delay_minutes"))
        page.sessions.all().delete()
        page.sections.all().delete()
        sections = {row["slug"]: EventPageSection.objects.create(page=page, **row) for row in data["sections"]}
        for row in data["sessions"]:
            values = dict(row)
            speakers = values.pop("speakers")
            values["track"] = sections.get(values["track"])
            values["room"] = sections.get(values["room"])
            session = EventSession.objects.create(page=page, delay_minutes=delays.get(values["slug"], 0), **values)
            for name in speakers:
                EventSessionSpeaker.objects.create(session=session, speaker=sections[name])
        changed = [key for key in PAGE_FIELDS if key in data]
        for key in changed:
            setattr(page, key, data[key])
        if changed:
            page.save(update_fields=changed)
        bump(page)
        audit(page, actor, "event.website_saved", revision=page.revision)
        return target


def set_release_locked(target, *, actor, released, revision):
    event_authority.require(actor, target, PUBLISH_SCHEDULE)
    require_feature(target, "events.website")
    if released and target.status != "published":
        raise ValidationError("Publish the event before releasing its website.")
    page = EventPage.objects.select_for_update().filter(**owner(target)).first()
    if page is None or page.revision != revision:
        raise ValidationError({"revision": "Save an occurrence page and reload before releasing it."})
    page.released = released
    bump(page)
    audit(page, actor, "event.website_released" if released else "event.website_unreleased", revision=page.revision)
    return page


@transaction.atomic
def set_release(target, *, actor, released, revision):
    target, actor = locked_target(target, actor, PUBLISH_SCHEDULE)
    return set_release_locked(target, actor=actor, released=released, revision=revision)


@transaction.atomic
def set_delay(target, slug, *, actor, minutes):
    target, actor = locked_target(target, actor, PUBLISH_SCHEDULE)
    if not 0 <= minutes <= 1440:
        raise ValidationError("Delay must be between zero and 1440 minutes.")
    page = EventPage.objects.select_for_update().filter(**owner(target)).first()
    if page is None:
        raise ValidationError("Create an occurrence override before changing its delays.")
    from django.shortcuts import get_object_or_404
    session = get_object_or_404(page.sessions, slug=slug)
    session.delay_minutes = minutes
    session.save(update_fields=["delay_minutes"])
    bump(page)
    audit(page, actor, "event.website_delay_changed", session_slug=slug, delay_minutes=minutes)
    return target
