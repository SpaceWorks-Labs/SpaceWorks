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
    from apps.makerspaces.public_page_authority import reject_platform
    reject_platform(actor)
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(target.makerspace_id)
    if isinstance(target, Event):
        series_id = Event.objects.values_list("series_id", flat=True).get(pk=target.pk)
        if series_id:
            EventSeries.objects.select_for_update().get(pk=series_id)
    target = type(target).objects.select_for_update().get(pk=target.pk)
    target.makerspace = require_module_locked(target.makerspace, "events")
    actor = lock_authority(actor, target)
    reject_platform(actor)
    event_authority.require(actor, target, permission)
    require_feature(target, "events.website")
    if target.status in {"cancelled", "completed"}:
        raise ValidationError("Terminal events are read-only.")
    return target, actor


def audit(page, actor, action, **meta):
    record(actor=actor, action=action, makerspace=page.makerspace, target=page, meta=meta)


def own_page(target, copies, asset_map=None, identity_map=None):
    page = EventPage.objects.select_for_update().filter(**owner(target)).first()
    if page is not None:
        return page
    if isinstance(target, Event) and target.series_id:
        page = copy_page(target, target, copies=copies, preserve_delays=True,
                         preserve_revision=True, asset_map=asset_map, identity_map=identity_map)
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
    legacy_order = "section_order" in data and "EDITORIAL" not in data["section_order"]
    legacy_enabled = "section_enabled" in data and "EDITORIAL" not in data["section_enabled"]
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
        if legacy_order:
            data["section_order"].remove("EDITORIAL")
            data["section_order"].insert(before["section_order"].index("EDITORIAL"), "EDITORIAL")
        if legacy_enabled:
            data["section_enabled"]["EDITORIAL"] = before["section_enabled"].get("EDITORIAL", True)
        from .website_revisions import validate_bodies
        validate_bodies(data, before)
        # An older full-content client must not erase newly added editorial fields.
        previous = {row["slug"]: row for row in before["sections"]}
        for row in data["sections"]:
            for key, default in SECTION_DETAIL_DEFAULTS.items():
                row.setdefault(key, previous.get(row["slug"], {}).get(key, default))
        section_fields = (*SECTION_FIELDS, "asset_id")
        if ([{key: row[key] for key in section_fields} for row in before["sections"]] != data["sections"]
                or any(data[key] != before[key] for key in PAGE_FIELDS if key in data)):
            event_authority.require(actor, target, EDIT_DETAILS)
        remapped, identity_map = {}, {}
        page = own_page(target, copies, asset_map=remapped, identity_map=identity_map)
        for row in data["sessions"]:
            if row.get("session_id") is not None and existing is None:
                if row["session_id"] not in identity_map:
                    raise ValidationError({"session_id": "Choose an inherited session identity."})
                row["session_id"] = identity_map[row["session_id"]]
        # Resolve exact inherited asset IDs, including renamed/new sections.
        if existing is None and remapped:
            for row in data["sections"]:
                if row["asset_id"] is not None:
                    if row["asset_id"] not in remapped:
                        raise ValidationError("Images must belong to the inherited page.")
                    row["asset_id"] = remapped[row["asset_id"]]
            if "editorial_document" in data:
                editorial = data["editorial_document"]
                if editorial.get("cover_asset_id") is not None:
                    if editorial["cover_asset_id"] not in remapped:
                        raise ValidationError("Cover must belong to the inherited page.")
                    editorial["cover_asset_id"] = remapped[editorial["cover_asset_id"]]
                for group in editorial["sections"]:
                    if group["type"] == "gallery":
                        for item in group["payload"]["items"]:
                            if item["asset_id"] not in remapped:
                                raise ValidationError("Gallery images must belong to the inherited page.")
                            item["asset_id"] = remapped[item["asset_id"]]
        assets = set(page.assets.values_list("pk", flat=True))
        _validate_content(target, data, assets)
        # Schedule fields belong to publish_schedule; detail editors cannot smuggle them.
        if not event_authority.can(actor, target, PUBLISH_SCHEDULE):
            current = project(target)["sessions"]
            fields = ("slug", "title", "body", "starts_at", "ends_at", "track", "room", "speakers", "visibility")
            if ([{key: row[key] for key in fields} for row in current]
                    != [{key: row[key] for key in fields} for row in data["sessions"]]):
                raise ValidationError("Schedule changes require publish_schedule.")
            by_slug = {row["slug"]: row["session_id"] for row in current}
            if any(row.get("session_id") is not None and str(row["session_id"]) != by_slug.get(row["slug"])
                   for row in data["sessions"]):
                raise ValidationError({"session_id": "Changing session identity requires publish_schedule."})
        from .website_session_identity import reconcile
        sessions = reconcile(page, data["sessions"])
        page.sessions.all().delete()
        page.sections.all().delete()
        sections = {row["slug"]: EventPageSection.objects.create(page=page, **row) for row in data["sections"]}
        for row in sessions:
            values = dict(row)
            speakers = values.pop("speakers")
            values["track"] = sections.get(values["track"])
            values["room"] = sections.get(values["room"])
            session = EventSession.objects.create(page=page, **values)
            for name in speakers:
                EventSessionSpeaker.objects.create(session=session, speaker=sections[name])
        changed = [key for key in PAGE_FIELDS if key in data]
        for key in changed:
            setattr(page, key, data[key])
        if changed:
            page.save(update_fields=changed)
        from .website_revisions import save_draft
        save_draft(page, actor)
        bump(page)
        audit(page, actor, "event.website_saved", revision=page.revision)
        return target


def set_release_locked(target, *, actor, released, revision):
    from apps.makerspaces.public_page_authority import reject_platform
    reject_platform(actor)
    event_authority.require(actor, target, PUBLISH_SCHEDULE)
    require_feature(target, "events.website")
    if released and target.status != "published":
        raise ValidationError("Publish the event before releasing its website.")
    page = EventPage.objects.select_for_update().filter(**owner(target)).first()
    if page is None or page.revision != revision:
        raise ValidationError({"revision": "Save an occurrence page and reload before releasing it."})
    if released:
        from .website_revisions import validate_snapshot_window
        if page.draft_revision_id is None:
            raise ValidationError({"revision": "Save a draft before releasing it."})
        validate_snapshot_window(target, page.draft_revision)
        if isinstance(target, EventSeries):
            for occurrence in target.occurrences.filter(website_page__isnull=True).select_for_update().order_by("pk"):
                validate_snapshot_window(occurrence, page.draft_revision, inherited=True)
        page.published_revision = page.draft_revision
        page.save(update_fields=["published_revision"])
    page.released = released
    bump(page)
    audit(page, actor, "event.website_released" if released else "event.website_unreleased", revision=page.revision)
    return page


@transaction.atomic
def set_release(target, *, actor, released, revision):
    target, actor = locked_target(target, actor, PUBLISH_SCHEDULE)
    return set_release_locked(target, actor=actor, released=released, revision=revision)


from .website_delays import set_delay  # noqa: E402,F401
