"""Capture working content once. Public operational edits copy publication only."""

import json
from copy import deepcopy
from datetime import datetime
from rest_framework.exceptions import ValidationError
from apps.makerspaces.public_page_markdown import rendering_policy, validate_markdown
from apps.makerspaces.public_page_contract import empty_document, reference_slots
from .models_website_revisions import EventPageRevision, EventPageRevisionAsset, EventPageRevisionMember


def working_document(page):
    from .website_projection import project_page
    document = project_page(page.event or page.series, page, snapshot=False)
    document.pop("assets", None)
    for key in ("revision", "released", "inherited", "draft_revision_id", "published_revision_id", "delay_targets"):
        document.pop(key, None)
    for group in ("sections", "sessions"):
        for row in document[group]:
            for key in ("image_url", "image_alt_text", "effective_starts_at", "effective_ends_at"):
                row.pop(key, None)
            row["body_rendering"] = rendering_policy(row["body"])
    document["editorial_document"] = deepcopy(page.editorial_document or empty_document("event"))
    return document


def append_snapshot(page, *, actor=None, document=None, anchor=None, source_revision=None):
    from .website_projection import window
    if document is None:
        document = working_document(page)
    document = json.loads(json.dumps(document, default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value)))
    assets = {f"section:{row['slug']}": row["asset_id"] for row in document["sections"] if row.get("asset_id") is not None}
    if source_revision is None:
        editorial_assets, members = reference_slots(document["editorial_document"])
    else:
        editorial = deepcopy(document["editorial_document"])
        for section in editorial["sections"]:
            if section["type"] == "team":
                section["payload"]["entries"] = [row for row in section["payload"]["entries"] if row["kind"] != "member"]
        editorial_assets, _ = reference_slots(editorial)
        members = {str(row.slot): row.profile_id for row in source_revision.member_references.all()}
    if members and source_revision is None:
        # Member editorial slots use the same typed references as other pages.
        from apps.makerspaces.models_profiles import MemberProfile
        from apps.makerspaces.public_profile_access import profile_is_public
        profiles = {row.pk: row for row in MemberProfile.objects.filter(pk__in=members.values()).select_related(
            "membership__user", "membership__makerspace")}
        if any(not profile_is_public(profiles.get(pk)) for pk in members.values()):
            raise ValidationError("Choose currently public member profiles.")
        for section in document["editorial_document"]["sections"]:
            if section["type"] == "team":
                for row in section["payload"]["entries"]:
                    if row["kind"] == "member":
                        row.pop("profile_id")
                        row["member_slot_id"] = row["id"]
    assets.update({f"editorial:{slot}": pk for slot, pk in editorial_assets.items()})
    if set(page.assets.filter(pk__in=assets.values()).values_list("pk", flat=True)) != set(assets.values()):
        raise ValidationError("Snapshot images must belong to this page.")
    revision = EventPageRevision.objects.create(
        page=page, document=document, source_anchor_start=anchor or window(page.event or page.series)[0], created_by=actor)
    EventPageRevisionAsset.objects.bulk_create([
        EventPageRevisionAsset(revision=revision, slot=slot, asset_id=pk) for slot, pk in assets.items()])
    EventPageRevisionMember.objects.bulk_create([
        EventPageRevisionMember(revision=revision, slot=slot, profile_id=pk) for slot, pk in members.items()])
    return revision


def save_draft(page, actor=None):
    page.draft_revision = append_snapshot(page, actor=actor)
    page.save(update_fields=["draft_revision"])
    return page.draft_revision


def validate_bodies(data, before):
    for group in ("sections", "sessions"):
        old = {row["slug"]: row for row in before[group]}
        by_identity = {str(row.get("session_id")): row for row in before[group]} if group == "sessions" else {}
        for row in data[group]:
            previous = by_identity.get(str(row["session_id"]), {}) if row.get("session_id") else old.get(row["slug"], {})
            if row["body"] != previous.get("body"):
                row["body"] = validate_markdown(row["body"], legacy_http=True)


def validate_snapshot_window(target, revision, *, inherited=False):
    from .website_projection import window
    start, end = window(target)
    anchor = revision.source_anchor_start
    from .website_revision_projection import snapshot_sessions
    for row in snapshot_sessions(revision, public=True):
        lo, hi = datetime.fromisoformat(row["starts_at"]), datetime.fromisoformat(row["ends_at"])
        if inherited:
            lo, hi = start + (lo - anchor), start + (hi - anchor)
        if not start <= lo < hi <= end:
            raise ValidationError("The window excludes sessions in the released website. Release a fitting draft or unrelease it first.")


def operational_snapshot(page, identity, minutes, actor):
    revision = page.published_revision
    document = deepcopy(revision.document)
    for row in document["sessions"]:
        if row["session_id"] == str(identity):
            row["delay_minutes"] = minutes
    return append_snapshot(page, actor=actor, document=document, anchor=revision.source_anchor_start, source_revision=revision)


def refresh_owner_anchor(target, actor):
    from .website_copy import owner
    from .models_website import EventPage
    from .website_projection import window
    from .services_website import bump, audit
    page = EventPage.objects.select_for_update().filter(**owner(target)).first()
    if page and page.draft_revision_id and page.draft_revision.source_anchor_start != window(target)[0]:
        save_draft(page, actor)
        bump(page)
        audit(page, actor, "event.website_saved", revision=page.revision, reason="owner_anchor_changed")
