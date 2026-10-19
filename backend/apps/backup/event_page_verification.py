"""Retained event snapshots remain verifiable with the Events runtime tombstoned."""

from datetime import datetime

from django.apps import apps
from django.db.models import Q

from .public_page_verification import refuse, verify_asset, verify_pointers, verify_references
from .event_page_draft_verification import owner_window, verify_released_window, verify_working_draft


def verify_event_pages(*, using):
    from apps.makerspaces.public_page_contract import validate_stored_document
    Page = apps.get_model("events.EventPage")
    count = 0
    for page in Page.objects.using(using).select_related("event", "series").iterator(chunk_size=100):
        verify_pointers(page)
        target = page.event or page.series
        if target.makerspace_id != page.makerspace_id:
            refuse("event venue differs from page owner")
        lo, hi = owner_window(target)
        if page.sessions.filter(Q(starts_at__lt=lo) | Q(ends_at__gt=hi)).exists():
            refuse("working session outside owner window")
        identities = set(page.session_identities.values_list("pk", flat=True))
        aliases = {(row.slug, row.identity_id) for row in page.session_aliases.all()}
        if any(identity not in identities for _, identity in aliases):
            refuse("foreign session alias identity")
        for session in page.sessions.all():
            if session.identity_id not in identities or (session.slug, session.identity_id) not in aliases:
                refuse("missing working session identity or alias")
            if session.starts_at >= session.ends_at:
                refuse("nonpositive working session interval")
            for section in (session.track, session.room):
                if section is not None and section.page_id != page.pk:
                    refuse("foreign working programme section")
            if session.speaker_links.exclude(speaker__page=page).exists():
                refuse("foreign working speaker")
        for revision in page.revisions.all():
            if revision.schema_version != 1:
                refuse("unsupported event snapshot schema")
            try:
                validate_stored_document(revision.document["editorial_document"], kind="event")
                verify_references(revision, revision.document, event=True)
                _verify_sessions(revision.document, identities, aliases)
            except (KeyError, TypeError, ValueError):
                refuse("malformed event snapshot")
        for asset in page.assets.all():
            verify_asset(asset, "event", page.makerspace_id, using)
        if page.series_id:
            # An occurrence with its own page does not inherit, even if unreleased.
            inheritors = target.occurrences.filter(website_page__isnull=True)
            for event in inheritors:
                if page.sessions.filter(ends_at__gt=lo + (event.ends_at - event.starts_at)).exists():
                    refuse("working inherited session outside occurrence window")
                if page.released:
                    verify_released_window(event, page.published_revision, inherited=True)
        if page.released:
            verify_released_window(target, page.published_revision)
        verify_working_draft(page)
        count += 1
    return count


def _verify_sessions(document, identities, aliases):
    from uuid import UUID
    from apps.makerspaces.public_page_markdown import validate_markdown
    ids, slugs = set(), set()
    sections = {row["slug"]: row for row in document["sections"]}
    if len(sections) != len(document["sections"]):
        refuse("duplicate programme section slug")
    for row in document["sessions"]:
        identity = UUID(row["session_id"])
        if (identity not in identities or (row["slug"], identity) not in aliases
                or identity in ids or row["slug"] in slugs):
            refuse("snapshot session identity or permanent alias")
        ids.add(identity)
        slugs.add(row["slug"])
        lo, hi = datetime.fromisoformat(row["starts_at"]), datetime.fromisoformat(row["ends_at"])
        if lo.tzinfo is None or hi.tzinfo is None or lo >= hi:
            refuse("invalid snapshot session interval")
        for field, kind in (("track", "track"), ("room", "room")):
            if row.get(field) is not None and sections.get(row[field], {}).get("kind") != kind:
                refuse("snapshot programme section reference")
        if any(sections.get(slug, {}).get("kind") != "speaker" for slug in row["speakers"]):
            refuse("snapshot speaker reference")
    for row in [*document["sections"], *document["sessions"]]:
        policy = row.get("body_rendering")
        if policy not in {"restricted_v1", "legacy_literal_v1"}:
            refuse("unsupported prose rendering policy")
        if policy == "restricted_v1":
            validate_markdown(row["body"], legacy_http=True)
