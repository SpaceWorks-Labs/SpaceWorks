"""Explicit website clone/copy-on-write adapter; no shared deletable keys."""

from apps.makerspaces.resource_clone import bounded_children, copy_fields
from apps.makerspaces import website_assets

from .models import EventSeries
from .models_website import EventPage, EventPageAsset, EventPageSection, EventSession, EventSessionSpeaker
from .website_projection import window
from .website_visibility import effective_page
from .website_content import PAGE_FIELDS, SECTION_FIELDS

SESSION_FIELDS = ("slug", "title", "body", "visibility", "starts_at", "ends_at")


def copy_page(source, target, *, copies, preserve_delays=False, preserve_revision=False, asset_map=None):
    """Caller holds source/target locks and the durable asset-copy transaction."""
    original = (EventPage.objects.filter(series=source).first()
                if isinstance(source, EventSeries) else effective_page(source))
    if original is None:
        return None
    original = EventPage.objects.select_for_update().get(pk=original.pk)
    # An occurrence override continues the inherited optimistic concurrency token.
    prepared_id = getattr(copies, "prepared_page_id", None)
    page = EventPage.objects.create(**({"id": prepared_id} if prepared_id else {}), makerspace=target.makerspace,
                                    revision=original.revision if preserve_revision else 1,
                                    **copy_fields(original, PAGE_FIELDS),
                                    **owner(target))
    assets = {}
    for row in bounded_children(original.assets.select_related("page__makerspace")):
        key = website_assets.copy_asset(row, page, module="events", copies=copies)
        assets[row.pk] = EventPageAsset.objects.create(
            page=page, object_key=key, size_bytes=row.size_bytes, alt_text=row.alt_text)
    if asset_map is not None:
        asset_map.update({source_id: row.pk for source_id, row in assets.items()})
    sections = {}
    for row in bounded_children(original.sections.all()):
        values = copy_fields(row, SECTION_FIELDS)
        if source.pk != target.pk and row.kind in ("prizes", "judges", "mentors", "project_gallery", "results"):
            options = dict(values["options"])
            if row.kind == "prizes" and options.get("ids"):
                from .judging.models_definitions import HackathonPrize
                originals = list(HackathonPrize.objects.filter(event=source).order_by("order", "pk").values_list("pk", flat=True))
                copied = list(HackathonPrize.objects.filter(event=target).order_by("order", "pk").values_list("pk", flat=True))
                mapping = dict(zip(originals, copied))
                options["ids"] = [mapping[pk] for pk in options["ids"] if pk in mapping]
            else:
                # People, project entries and publication history never clone.
                options["ids"] = []
            values["options"] = options
        sections[row.pk] = EventPageSection.objects.create(
            page=page, asset=assets.get(row.asset_id), **values)
    anchor = original.series if original.series_id else original.event
    delta = window(target)[0] - window(anchor)[0]
    for row in bounded_children(original.sessions.prefetch_related("speaker_links__speaker"), maximum=200):
        values = copy_fields(row, SESSION_FIELDS)
        values["starts_at"] += delta
        values["ends_at"] += delta
        session = EventSession.objects.create(page=page, delay_minutes=row.delay_minutes if preserve_delays else 0, track=sections.get(row.track_id),
                                               room=sections.get(row.room_id), **values)
        for speaker in [link.speaker for link in row.speaker_links.all()]:
            EventSessionSpeaker.objects.create(session=session, speaker=sections[speaker.pk])
    return page


def owner(target):
    return {"series" if isinstance(target, EventSeries) else "event": target}
